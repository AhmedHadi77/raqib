"""MQTT client for the robot (paho-mqtt 2.x).

Topics (robot_id = robot01):
  robot/{id}/telemetry  robot -> cloud   periodic JSON telemetry
  robot/{id}/events     robot -> cloud   obstacle_stop, safe_hold, gas_alert, state_change ...
  robot/{id}/acks       robot -> cloud   result of each command (matched by command id)
  robot/{id}/status     robot -> cloud   retained {"online": true/false}  (last-will = offline)
  robot/{id}/info       robot -> cloud   retained capabilities + zone list
  robot/{id}/commands   cloud -> robot   {"v":1,"id":"...","action":"move","params":{...}}
  robot/{id}/heartbeat  cloud -> robot   every ~2 s; missing for 10 s => SAFE HOLD
"""
from __future__ import annotations

import json
import logging
import ssl
import threading
import time

import paho.mqtt.client as mqtt

from . import discovery

log = logging.getLogger(__name__)
SCHEMA_VERSION = 1


class RobotMqttClient:
    def __init__(self, cfg: dict, on_command, on_heartbeat, on_connect_change=None):
        self.cfg = cfg
        m = cfg["mqtt"]
        self.robot_id = cfg["robot_id"]
        self.base = f"robot/{self.robot_id}"
        self.on_command = on_command
        self.on_heartbeat = on_heartbeat
        self.on_connect_change = on_connect_change or (lambda c: None)
        self.connected = False
        self.info_payload: dict = {}

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{self.robot_id}-edge",
                                  protocol=mqtt.MQTTv311, clean_session=True)
        if m.get("username"):
            self.client.username_pw_set(m["username"], m.get("password"))
        if m.get("tls"):
            self.client.tls_set(ca_certs=m.get("ca_cert"), certfile=m.get("client_cert"),
                                keyfile=m.get("client_key"), tls_version=ssl.PROTOCOL_TLS_CLIENT)
        self.client.will_set(f"{self.base}/status", json.dumps({"online": False}), qos=1, retain=True)
        self.client.reconnect_delay_set(min_delay=1, max_delay=10)
        self.client.max_queued_messages_set(200)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def start(self):
        m = self.cfg["mqtt"]
        self._loop_started = False
        self._stop_evt = threading.Event()
        self.server: tuple[str, int] | None = None
        if discovery.is_auto(m.get("host")):
            log.info("MQTT host is 'auto': looking for the Raqib server on the local network (UDP %s)",
                     discovery.DISCOVERY_PORT)
            threading.Thread(target=self._discovery_loop, daemon=True, name="server-discovery").start()
        else:
            self._connect_to(m["host"], int(m["port"]))

    def _connect_to(self, host: str, port: int):
        m = self.cfg["mqtt"]
        self.server = (host, port)
        log.info("MQTT connecting to %s:%s (tls=%s)", host, port, m.get("tls"))
        self.client.connect_async(host, port, keepalive=int(m.get("keepalive", 20)))
        if not self._loop_started:
            self.client.loop_start()
            self._loop_started = True

    def _discovery_loop(self):
        """Connect to the last known server at once, then follow the beacon: if we stay disconnected,
        listen again and switch to whatever address the server announces now (e.g. the PC got a new IP)."""
        cached = discovery.load_cache()
        if cached and cached.get("host"):
            log.info("Trying the last known server %s", cached["host"])
            self._connect_to(cached["host"], int(cached.get("port", 1883)))
        last_ok, last_hint = time.time(), 0.0
        while not self._stop_evt.is_set():
            if self.connected:
                last_ok = time.time()
                self._stop_evt.wait(2)
                continue
            if self.server is not None and time.time() - last_ok < 12:
                self._stop_evt.wait(1)      # give a (re)connect a moment before hunting for a new address
                continue
            found = discovery.listen(timeout_s=5, port=discovery.DISCOVERY_PORT, stop=self._stop_evt)
            if found:
                discovery.save_cache(found)
                if self.server != (found["host"], found["port"]):
                    log.info("Found the Raqib server '%s' at %s", found.get("site") or "", found["host"])
                    self._connect_to(found["host"], found["port"])
                last_ok = time.time()
            elif time.time() - last_hint > 30:
                last_hint = time.time()
                log.warning("Still looking for the Raqib server. Is start_backend.bat running on the PC, on the "
                            "same Wi-Fi as the robot? (or set mqtt.host to the PC's IP in config.local.yaml)")

    def stop(self):
        if getattr(self, "_stop_evt", None):
            self._stop_evt.set()
        try:
            if self.connected:
                self.publish("status", {"online": False}, qos=1, retain=True)
                time.sleep(0.2)
            self.client.disconnect()
        finally:
            if getattr(self, "_loop_started", False):
                self.client.loop_stop()

    # ------------------------------------------------------------------ callbacks
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code.is_failure:
            log.error("MQTT connect failed: %s", reason_code)
            return
        self.connected = True
        log.info("MQTT connected to %s", self.server[0] if getattr(self, "server", None) else "broker")
        try:  # disable Nagle: small command/ack packets must not wait ~40 ms (KPI: round-trip < 80 ms)
            import socket

            client.socket().setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:  # noqa: BLE001
            pass
        client.subscribe([(f"{self.base}/commands", 1), (f"{self.base}/heartbeat", 0)])
        self.publish("status", {"online": True, "ts": time.time()}, qos=1, retain=True)
        if self.info_payload:
            self.publish("info", self.info_payload, qos=1, retain=True)
        self.on_connect_change(True)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self.connected = False
        log.warning("MQTT disconnected (%s) - will retry", reason_code)
        self.on_connect_change(False)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8") or "{}")
        except Exception:  # noqa: BLE001
            log.warning("bad JSON on %s", msg.topic)
            return
        if msg.topic.endswith("/heartbeat"):
            self.on_heartbeat(payload)
        elif msg.topic.endswith("/commands"):
            self.on_command(payload)

    # ------------------------------------------------------------------ publish
    def publish(self, sub: str, payload: dict, qos: int = 0, retain: bool = False):
        payload.setdefault("v", SCHEMA_VERSION)
        payload.setdefault("robot_id", self.robot_id)
        self.client.publish(f"{self.base}/{sub}", json.dumps(payload, default=str), qos=qos, retain=retain)

    def set_info(self, info: dict):
        self.info_payload = info
        if self.connected:
            self.publish("info", info, qos=1, retain=True)
