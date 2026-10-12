"""Bridge between FastAPI (asyncio) and the robot over MQTT.

* keeps the latest telemetry / info / online status of every robot
* sends commands and awaits the matching ack (by command id) with a timeout
* publishes the cloud heartbeat the robot's safety loop watches (T-09)
* fans telemetry + events out to WebSocket listeners
"""
from __future__ import annotations

import asyncio
import json
import logging
import ssl
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import paho.mqtt.client as mqtt

from .config import Settings
from .schemas import Ack, Command

log = logging.getLogger(__name__)

Listener = Callable[[dict], Awaitable[None]]

LONG_ACTIONS = {"go_to_zone", "move", "turn", "read_environment", "sound_scan"}


@dataclass
class RobotState:
    robot_id: str
    online: bool = False
    telemetry: dict | None = None
    info: dict | None = None
    last_seen: float = 0.0
    events: list[dict] = field(default_factory=list)
    history: deque = field(default_factory=lambda: deque(maxlen=720))   # ~1 h at one sample / 5 s
    _last_hist: float = 0.0

    def record(self, t: dict, now: float):
        """Keep a compact sample every 5 s for the app's trend charts."""
        if now - self._last_hist < 5.0:
            return
        self._last_hist = now
        e = t.get("environment") or {}
        a = t.get("audio") or {}
        p = t.get("pose") or {}
        self.history.append({
            "ts": round(now, 1), "temperature_c": e.get("temperature_c"), "humidity_pct": e.get("humidity_pct"),
            "aqi": e.get("aqi"), "db": a.get("db"), "battery": (t.get("battery") or {}).get("percent"),
            "x": p.get("x"), "y": p.get("y"), "zone": p.get("zone"),
        })

    def summary(self) -> dict:
        t = self.telemetry or {}
        return {
            "robot_id": self.robot_id,
            "online": self.online and (time.time() - self.last_seen < 15),
            "last_seen": self.last_seen,
            "state": t.get("state"),
            "simulation": t.get("simulation", (self.info or {}).get("simulation")),
            "battery": t.get("battery"),
            "zone": (t.get("pose") or {}).get("zone"),
            "zones": list(((self.info or {}).get("zones") or {}).keys()),
        }


class RobotBridge:
    def __init__(self, settings: Settings):
        self.s = settings
        self.robots: dict[str, RobotState] = {}
        self.pending: dict[str, asyncio.Future] = {}
        self.listeners: set[Listener] = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.connected = False
        self._hb_task: asyncio.Task | None = None
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=f"backend-{int(time.time())}", protocol=mqtt.MQTTv311)
        if settings.mqtt_username:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        if settings.mqtt_tls:
            self.client.tls_set(ca_certs=settings.mqtt_ca_cert, tls_version=ssl.PROTOCOL_TLS_CLIENT)
        self.client.reconnect_delay_set(1, 10)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    # ------------------------------------------------------------------ lifecycle
    async def start(self):
        self.loop = asyncio.get_running_loop()
        self.robot(self.s.robot_id)
        log.info("MQTT bridge -> %s:%s", self.s.mqtt_host, self.s.mqtt_port)
        self.client.connect_async(self.s.mqtt_host, self.s.mqtt_port, keepalive=20)
        self.client.loop_start()
        self._hb_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self):
        if self._hb_task:
            self._hb_task.cancel()
        self.client.disconnect()
        self.client.loop_stop()

    def robot(self, robot_id: str) -> RobotState:
        if robot_id not in self.robots:
            self.robots[robot_id] = RobotState(robot_id)
        return self.robots[robot_id]

    # ------------------------------------------------------------------ paho callbacks (paho thread)
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code.is_failure:
            log.error("MQTT connect failed: %s", reason_code)
            return
        self.connected = True
        log.info("MQTT bridge connected")
        try:  # disable Nagle: small command/ack packets must not wait ~40 ms (KPI: round-trip < 80 ms)
            import socket

            client.socket().setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:  # noqa: BLE001
            pass
        client.subscribe([("robot/+/telemetry", 0), ("robot/+/events", 1), ("robot/+/acks", 1),
                          ("robot/+/status", 1), ("robot/+/info", 1)])

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self.connected = False
        log.warning("MQTT bridge disconnected: %s", reason_code)

    def _on_message(self, client, userdata, msg):
        try:
            parts = msg.topic.split("/")
            robot_id, kind = parts[1], parts[2]
            payload = json.loads(msg.payload.decode("utf-8") or "{}")
        except Exception:  # noqa: BLE001
            return
        if self.loop:
            self.loop.call_soon_threadsafe(self._handle, robot_id, kind, payload)

    # ------------------------------------------------------------------ asyncio side
    def _handle(self, robot_id: str, kind: str, payload: dict):
        r = self.robot(robot_id)
        now = time.time()
        if kind == "telemetry":
            r.telemetry, r.last_seen, r.online = payload, now, True
            r.record(payload, now)
        elif kind == "status":
            r.online = bool(payload.get("online"))
            if r.online:
                r.last_seen = now
        elif kind == "info":
            r.info = payload
        elif kind == "events":
            r.events = (r.events + [payload])[-100:]
            r.last_seen = now
        elif kind == "acks":
            fut = self.pending.pop(payload.get("id", ""), None)
            if fut and not fut.done():
                fut.set_result(payload)
            return
        self._broadcast({"kind": kind, "robot_id": robot_id, "data": payload})

    def _broadcast(self, msg: dict):
        for cb in list(self.listeners):
            asyncio.create_task(self._safe(cb, msg))

    async def _safe(self, cb: Listener, msg: dict):
        try:
            await cb(msg)
        except Exception:  # noqa: BLE001
            self.listeners.discard(cb)

    async def broadcast(self, msg: dict):
        self._broadcast(msg)

    async def _heartbeat_loop(self):
        while True:
            if self.connected:
                for rid in list(self.robots):
                    self.client.publish(f"robot/{rid}/heartbeat", json.dumps({"ts": time.time()}), qos=0)
            await asyncio.sleep(self.s.heartbeat_interval_s)

    # ------------------------------------------------------------------ commands
    def is_online(self, robot_id: str) -> bool:
        r = self.robots.get(robot_id)
        return bool(r and r.online and time.time() - r.last_seen < 15)

    async def send(self, robot_id: str, action: str, params: dict[str, Any] | None = None,
                   timeout: float | None = None, issued_by: str | None = None, wait: bool = True) -> Ack:
        cmd = Command(action=action, params=params or {}, issued_by=issued_by)
        if not self.connected:
            return Ack(id=cmd.id, action=action, status="error", error="backend is not connected to the MQTT broker")
        if not self.is_online(robot_id) and action not in ("estop", "stop"):
            return Ack(id=cmd.id, action=action, status="error", error=f"robot '{robot_id}' is offline")
        if timeout is None:
            timeout = self.s.navigation_timeout_s if action in LONG_ACTIONS else self.s.command_timeout_s
        fut = self.loop.create_future() if wait else None
        if fut:
            self.pending[cmd.id] = fut
        self.client.publish(f"robot/{robot_id}/commands", cmd.model_dump_json(), qos=1)
        if not wait:
            return Ack(id=cmd.id, action=action, status="ok", result={"sent": True})
        try:
            raw = await asyncio.wait_for(fut, timeout)
            return Ack(**raw)
        except asyncio.TimeoutError:
            self.pending.pop(cmd.id, None)
            return Ack(id=cmd.id, action=action, status="timeout", error=f"no reply within {timeout:.0f}s")

    async def ping(self, robot_id: str) -> float | None:
        t0 = time.perf_counter()
        ack = await self.send(robot_id, "ping", timeout=5)
        return round((time.perf_counter() - t0) * 1000, 1) if ack.status == "ok" else None
