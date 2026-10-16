"""IMU + wheel-encoder + battery polling and dead-reckoning odometry (50 Hz).

Two ways to measure distance:
  encoders  - slot-disc encoders count wheel turns (full build, or `hardware.encoders: true`)
  time      - no encoders (the reliable budget build): distance = wheel speed x time, where the wheel speed
              comes from the power actually sent to the motors and the calibrated `motion.max_speed_mps`
              (python -m hwtest.test_motors --calibrate). Heading always comes from the MPU6050.
"""
from __future__ import annotations

import math
import threading
import time

from .hal.base import BatteryReading, Hardware, ImuReading
from .motor_controller import MotorController


def angle_diff(target_deg: float, current_deg: float) -> float:
    """Smallest signed difference target - current in (-180, 180]."""
    return (target_deg - current_deg + 180.0) % 360.0 - 180.0


class SensorReader:
    """Fuses encoder distance with IMU heading into an (x, y, heading) pose estimate.

    Encoders give distance, the gyro gives heading (more reliable than wheel
    differences on a skid-steer 4WD chassis). Single-channel encoders cannot tell
    direction, so the sign comes from the current motor command.
    """

    def __init__(self, hw: Hardware, motors: MotorController, cfg: dict):
        self.hw, self.motors = hw, motors
        m = cfg.get("motion", {})
        self.m_per_tick = math.pi * float(m.get("wheel_diameter_m", 0.065)) / float(m.get("encoder_ticks_per_rev", 20))
        self.lock = threading.Lock()
        self.x = self.y = 0.0
        self.distance = 0.0          # signed cumulative travel (m)
        self.odometer = 0.0          # absolute travel (m)
        self.heading = 0.0           # deg, CCW positive, 0 = facing +x at start
        self._yaw_offset = None
        self.imu = ImuReading()
        self.battery = BatteryReading(None, None)
        self._last_ticks = hw.encoders.ticks()
        mode = str(m.get("odometry", "auto")).lower()
        self.use_encoders = mode == "encoders" or (mode == "auto" and bool(hw.extra.get("encoders", True)))
        self.max_speed = float(m.get("max_speed_mps", 0.5))
        self.deadband = float(hw.extra.get("motor_deadband", m.get("motor_deadband", 0.15)))
        self._last_t = time.monotonic()
        self._stop = threading.Event()
        self._bat_t = 0.0
        self._t = threading.Thread(target=self._loop, name="sensor-reader", daemon=True)
        self._t.start()

    def _loop(self):
        while not self._stop.is_set():
            imu = self.hw.imu.read()
            if self._yaw_offset is None:
                self._yaw_offset = imu.yaw_deg
            now_t = time.monotonic()
            dt, self._last_t = min(0.2, now_t - self._last_t), now_t
            if self.use_encoders:
                tl, tr = self.hw.encoders.ticks()
                dl = (tl - self._last_ticks[0]) * self.m_per_tick
                dr = (tr - self._last_ticks[1]) * self.m_per_tick
                self._last_ticks = (tl, tr)
                sl = -1.0 if self.motors.left < 0 else 1.0
                sr = -1.0 if self.motors.right < 0 else 1.0
                d = (sl * dl + sr * dr) / 2.0
            else:
                pl, pr = getattr(self.hw.motors, "applied", None) or (self.motors.left, self.motors.right)
                d = (self.wheel_speed(pl) + self.wheel_speed(pr)) / 2.0 * dt
            with self.lock:
                self.imu = imu
                self.heading = angle_diff(imu.yaw_deg - self._yaw_offset, 0.0)
                h = math.radians(self.heading)
                self.x += d * math.cos(h)
                self.y += d * math.sin(h)
                self.distance += d
                self.odometer += abs(d)
            now = time.monotonic()
            if now - self._bat_t > 2.0:
                self._bat_t = now
                try:
                    self.battery = self.hw.battery.read()
                except Exception:  # noqa: BLE001
                    pass
            self._stop.wait(0.02)

    def wheel_speed(self, power: float) -> float:
        """Ground speed (m/s) of one side at a motor power in [-1, 1]: nothing below the dead band
        (the motors do not turn), then linear up to max_speed_mps at full power."""
        a = abs(power)
        if a <= self.deadband:
            return 0.0
        return math.copysign(self.max_speed * (a - self.deadband) / (1.0 - self.deadband), power)

    def pose(self) -> dict:
        with self.lock:
            return {"x": round(self.x, 3), "y": round(self.y, 3), "heading_deg": round(self.heading, 1),
                    "odometer_m": round(self.odometer, 2)}

    def reset_pose(self, x: float = 0.0, y: float = 0.0, heading_deg: float = 0.0):
        with self.lock:
            self.x, self.y = x, y
            self._yaw_offset = self.imu.yaw_deg - heading_deg
            self.heading = heading_deg

    def close(self):
        self._stop.set()
