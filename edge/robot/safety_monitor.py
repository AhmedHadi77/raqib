"""Dedicated 100 Hz safety loop (Figure 2: Edge Safety Control Flow).

Runs independently of the cloud and of every other module. It can override all
other commands:
  * obstacle closer than stop_distance -> brake + block forward motion (T-01)
  * no cloud heartbeat for cloud_timeout_s -> SAFE HOLD (T-09)
  * low battery -> event
"""
from __future__ import annotations

import logging
import threading
import time

from .hal.base import Hardware
from .motor_controller import MotorController

log = logging.getLogger(__name__)


class SafetyMonitor:
    def __init__(self, hw: Hardware, motors: MotorController, cfg: dict, on_event=None):
        s = cfg.get("safety", {})
        self.hw, self.motors = hw, motors
        self.stop_cm = float(s.get("stop_distance_cm", 15))
        self.clear_cm = float(s.get("clear_distance_cm", 22))
        self.side_stop_cm = float(s.get("side_stop_distance_cm", 10))
        self.period = 1.0 / float(s.get("loop_hz", 100))
        self.cloud_timeout = float(s.get("cloud_timeout_s", 10))
        self.low_batt = float(s.get("low_battery_pct", 10))
        self.on_event = on_event or (lambda kind, data: None)

        self.distances = {"left": 400.0, "center": 400.0, "right": 400.0}
        self.blocked = False
        self.safe_hold = False
        self.last_heartbeat = time.monotonic()
        self.last_stop_latency_ms: float | None = None
        self.max_loop_ms = 0.0
        self.stop_count = 0
        self._low_batt_sent = False
        self.battery_pct_getter = None
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, name="safety-100hz", daemon=True)
        self._t.start()

    def heartbeat(self):
        self.last_heartbeat = time.monotonic()

    def _loop(self):
        while not self._stop.is_set():
            t0 = time.perf_counter()
            try:
                self._tick(t0)
            except Exception as e:  # noqa: BLE001 - the safety loop must never die
                log.exception("safety tick error: %s", e)
                self.motors.brake()
            dt = time.perf_counter() - t0
            self.max_loop_ms = max(self.max_loop_ms * 0.999, dt * 1000)
            time.sleep(max(0.0, self.period - dt))

    def _tick(self, t0: float):
        d = self.hw.ultrasonics.read_cm()
        self.distances = d
        front = d.get("center", 400.0)
        side = min(d.get("left", 400.0), d.get("right", 400.0))
        danger = front < self.stop_cm or side < self.side_stop_cm

        if danger and not self.blocked:
            moving_fwd = self.motors.net_forward() > 0.02
            self.motors.forward_blocked = True
            if moving_fwd:
                self.motors.brake()
            latency = (time.perf_counter() - t0) * 1000.0
            self.blocked = True
            if moving_fwd:
                self.stop_count += 1
                self.last_stop_latency_ms = round(latency + self.period * 1000.0, 2)  # worst case incl. sample age
                log.warning("OBSTACLE STOP: %s cm (latency %.2f ms)", d, self.last_stop_latency_ms)
                self.hw.speaker.beep("warning")
                self.on_event("obstacle_stop", {"distances_cm": d, "latency_ms": self.last_stop_latency_ms})
        elif self.blocked and front > self.clear_cm and side > self.side_stop_cm + 5:
            self.blocked = False
            self.motors.forward_blocked = False
            self.on_event("obstacle_cleared", {"distances_cm": d})

        # cloud watchdog
        silent = time.monotonic() - self.last_heartbeat
        if silent > self.cloud_timeout and not self.safe_hold:
            self.safe_hold = True
            self.motors.hold = True
            self.motors.brake()
            log.error("No cloud heartbeat for %.1fs -> SAFE HOLD", silent)
            self.on_event("safe_hold", {"silent_s": round(silent, 1)})
        elif self.safe_hold and silent < 2.0:
            self.safe_hold = False
            self.on_event("cloud_restored", {})

        if self.battery_pct_getter:
            pct = self.battery_pct_getter()
            if pct is not None and pct < self.low_batt and not self._low_batt_sent:
                self._low_batt_sent = True
                self.on_event("low_battery", {"percent": pct})

    def status(self) -> dict:
        return {
            "blocked": self.blocked,
            "safe_hold": self.safe_hold,
            "stop_distance_cm": self.stop_cm,
            "last_stop_latency_ms": self.last_stop_latency_ms,
            "stop_count": self.stop_count,
            "max_loop_ms": round(self.max_loop_ms, 2),
            "cloud_silent_s": round(time.monotonic() - self.last_heartbeat, 1),
        }

    def close(self):
        self._stop.set()
