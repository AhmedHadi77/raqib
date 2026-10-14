"""RobotApp - wires every edge module together and executes cloud commands.

Commands (robot/{id}/commands, JSON {"id","action","params"}):
  drive        {left, right}            manual tele-op (dead-man: stops if not repeated)
  move         {distance_m, speed?}     closed-loop straight move (negative = reverse)
  turn         {angle_deg}              turn in place (+ = left / counter-clockwise)
  go_to_zone   {zone}                   dead-reckoning navigation + reactive avoidance
  go_to_point  {x, y, heading_deg?}     same, to any point (patrol routes inside a room)
  set_home     {}                       reset pose to (0,0,0)
  stop         {}                       stop motion, back to IDLE
  estop        {}                       EMERGENCY STOP (latched)
  reset        {}                       clear EMERGENCY STOP
  pan_tilt     {pan, tilt}
  snapshot     {size?}                  JPEG base64 for the VLM
  read_environment {fresh?, occupied?}  averaged climate (AHT20+BMP280 or BME680) + MQ-135 reading + verdicts
  listen_audio {seconds?}               acoustic classification (+ voice_like, dB)
  sound_scan   {step_deg?, seconds?}    turn on the spot, measure loudness every step, face the loudest
  speak        {text}
  set_privacy  {enabled}
  webrtc_offer {sdp, type}              returns the WebRTC answer
  ping         {}                       latency test (KPI: MQTT round-trip < 80 ms)
  status       {}
"""
from __future__ import annotations

import asyncio
import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .audio_analyzer import AudioAnalyzer
from .camera_streamer import HAVE_AIORTC, CameraStreamer
from .environmental_sensor import EnvironmentalSensor
from .hal import create_hardware
from .motor_controller import MotorController
from .mqtt_client import RobotMqttClient
from .safety_monitor import SafetyMonitor
from .sensor_reader import SensorReader, angle_diff
from .state_machine import State, StateMachine

log = logging.getLogger(__name__)

MOTION_ACTIONS = {"move", "turn", "go_to_zone", "go_to_point", "drive", "sound_scan"}


class CommandError(Exception):
    def __init__(self, status: str, message: str, result: dict | None = None):
        super().__init__(message)
        self.status, self.message, self.result = status, message, result or {}


class RobotApp:
    def __init__(self, cfg: dict, hw=None, connect_mqtt: bool = True):
        self.cfg = cfg
        self.robot_id = cfg["robot_id"]
        self.mcfg = cfg.get("motion", {})
        self.zones = cfg.get("zones", {})
        self.hw = hw or create_hardware(cfg)
        self.motors = MotorController(self.hw)
        self.state = StateMachine(on_change=self._on_state_change)
        self.sensors = SensorReader(self.hw, self.motors, cfg)
        self.safety = SafetyMonitor(self.hw, self.motors, cfg, on_event=self._on_safety_event)
        self.safety.battery_pct_getter = lambda: self.sensors.battery.percent
        self.env = EnvironmentalSensor(self.hw, cfg, on_alert=self._on_gas_alert)
        self.camera = CameraStreamer(self.hw, cfg)
        self.audio = AudioAnalyzer(self.hw, cfg)

        self.cancel_motion = threading.Event()
        self.motion_lock = threading.Lock()
        self.last_drive_cmd = 0.0
        self.pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="cmd")
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, name="asyncio", daemon=True).start()

        self.mqtt = None
        if connect_mqtt:
            self.mqtt = RobotMqttClient(cfg, self._on_command, self._on_heartbeat)
            self.mqtt.set_info(self.info())
        self._stop = threading.Event()
        self._telemetry_t = threading.Thread(target=self._telemetry_loop, name="telemetry", daemon=True)

    # =============================================================== lifecycle
    def start(self):
        if self.mqtt:
            self.mqtt.start()
        self._telemetry_t.start()
        if self.hw.simulated:
            self.hw.speaker.say("Inspection robot online")
        else:
            threading.Thread(target=self._announce_address, daemon=True, name="announce").start()
        log.info("Robot %s started (simulation=%s)", self.robot_id, self.hw.simulated)

    def _announce_address(self):
        """Real robot: say its network address out loud once it has one, so the phone can always reach it."""
        import socket

        ip = None
        for _ in range(60):
            if self._stop.is_set():
                return
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("10.255.255.255", 1))
                ip = s.getsockname()[0]
                s.close()
            except OSError:
                ip = None
            if ip and not ip.startswith("127."):
                break
            time.sleep(1)
        if ip and not ip.startswith("127."):
            spoken = " dot ".join(ip.split("."))
            self.hw.speaker.say(f"Raqib is ready. My address is {spoken}")
            log.info("Robot address: http://%s:8000", ip)
        else:
            self.hw.speaker.say("Raqib is ready")

    def shutdown(self):
        log.info("shutting down...")
        self._stop.set()
        self.cancel_motion.set()
        self.motors.shutdown()
        try:
            asyncio.run_coroutine_threadsafe(self.camera.close_webrtc(), self.loop).result(2)
        except Exception:  # noqa: BLE001
            pass
        for part in (self.safety, self.env, self.camera, self.audio, self.sensors):
            part.close()
        if self.mqtt:
            self.mqtt.stop()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.hw.close()

    def info(self) -> dict:
        return {
            "type": "info",
            "simulation": self.hw.simulated,
            "simulator": "webots" if self.hw.extra.get("webots") else ("2d" if self.hw.simulated else None),
            "zones": {k: {"x": v["x"], "y": v["y"], "radius": v.get("radius", 1.0)} for k, v in self.zones.items()},
            "map": self._map_info(),
            "patrols": {k: v.get("patrol") for k, v in self.zones.items() if v.get("patrol")},
            "camera": {"hfov_deg": float(self.cfg.get("camera", {}).get("hfov_deg", 62.2)),
                       "pan_range_deg": [-90, 90]},
            "virtual_wiring": "harness" in self.hw.extra,
            "fixed_camera": bool(self.hw.extra.get("fixed_camera")),
            "hardware_profile": self._profile(),
            "actions": sorted(["drive", "move", "turn", "go_to_zone", "go_to_point", "set_home", "stop", "estop", "reset",
                               "set_wiring", "wiring_status", "wiring_spec",
                               "pan_tilt", "snapshot", "read_environment", "listen_audio", "sound_scan", "speak",
                               "set_privacy", "webrtc_offer", "ping", "status", "recheck_hardware"]),
            "webrtc": HAVE_AIORTC,
            "audio_model": "edge_impulse" if self.audio.runner else "heuristic",
            "safety": {"stop_distance_cm": self.safety.stop_cm, "cloud_timeout_s": self.safety.cloud_timeout},
            "health": self.hw.health,
            "faults": self.hw.faults(),
            "server": self.mqtt.server[0] if self.mqtt and getattr(self.mqtt, "server", None) else None,
            "software": {"version": "2.4.0"},
        }

    def _profile(self) -> str:
        """'budget' = the RM 500 build (no servos, AHT20, webcam), 'full' = PCA9685 + servos, BME680, UPS."""
        ex = self.hw.extra
        if ex.get("build"):
            return ex["build"]
        if ex.get("webots"):
            return "full"
        return "full" if ex.get("pca") is not None and not ex.get("fixed_camera") else "budget"

    def _map_info(self) -> dict:
        """Floor-plan hints for the app's mini-map (walls/obstacles are only known in simulation)."""
        w = self.hw.extra.get("world")
        if w is None:
            return {"bounds": None, "obstacles": []}
        return {"bounds": list(w.bounds), "obstacles": [list(o) for o in w.obstacles]}

    # =============================================================== events
    def _publish_event(self, kind: str, data: dict):
        log.info("EVENT %s %s", kind, data)
        if self.mqtt:
            self.mqtt.publish("events", {"type": "event", "event": kind, "ts": time.time(), "data": data}, qos=1)

    def _on_state_change(self, old: State, new: State, reason: str):
        self._publish_event("state_change", {"from": old.value, "to": new.value, "reason": reason})

    def _on_safety_event(self, kind: str, data: dict):
        if kind == "safe_hold":
            self.cancel_motion.set()
            self.state.transition(State.SAFE_HOLD, "cloud heartbeat lost")
        elif kind == "cloud_restored":
            if self.state.state == State.SAFE_HOLD:
                self.motors.hold = False
                self.state.transition(State.IDLE, "cloud heartbeat restored")
        self._publish_event(kind, data)

    def _on_gas_alert(self, reading: dict):
        msg = ("Warning. Poor air quality detected. Please ventilate this room."
               if reading["gas_verdict"] == "WARNING"
               else "Danger. Hazardous gas level detected. Ventilate and leave the area.")
        self.hw.speaker.beep("alarm")
        self.hw.speaker.say(msg)
        self._publish_event("gas_alert", {"zone": self.current_zone(), **reading})

    def _on_heartbeat(self, payload: dict):
        self.safety.heartbeat()

    # =============================================================== telemetry
    def current_zone(self) -> str | None:
        p = self.sensors.pose()
        best, best_d = None, math.inf
        for name, z in self.zones.items():
            d = math.hypot(p["x"] - float(z["x"]), p["y"] - float(z["y"]))
            if d <= float(z.get("radius", 1.0)) and d < best_d:
                best, best_d = name, d
        return best

    def telemetry(self) -> dict:
        b = self.sensors.battery
        imu = self.sensors.imu
        pose = self.sensors.pose()
        pose["zone"] = self.current_zone()
        return {
            "type": "telemetry",
            "ts": time.time(),
            "state": self.state.state.value,
            "simulation": self.hw.simulated,
            "privacy_mode": self.camera.privacy,
            "battery": {"voltage": b.voltage, "percent": b.percent},
            "pose": pose,
            "ultrasonic_cm": self.safety.distances,
            "imu": {"yaw_deg": round(imu.yaw_deg, 1), "pitch_deg": round(imu.pitch_deg, 1),
                    "roll_deg": round(imu.roll_deg, 1)},
            "motors": {"left": round(self.motors.left, 2), "right": round(self.motors.right, 2)},
            "pan_tilt": {"pan": self.motors.pan, "tilt": self.motors.tilt},
            "environment": self.env.current(),
            "audio": self.audio.latest,
            "safety": self.safety.status(),
            "mqtt_connected": bool(self.mqtt and self.mqtt.connected),
            "faults": self.hw.faults(),
            "health": self.hw.health,
        }

    def _telemetry_loop(self):
        period = 1.0 / float(self.cfg.get("telemetry_hz", 2))
        while not self._stop.is_set():
            # dead-man for manual tele-op
            if self.state.state == State.MANUAL and time.monotonic() - self.last_drive_cmd > float(
                    self.mcfg.get("teleop_deadman_s", 0.6)) and self.motors.is_moving():
                self.motors.stop()
            if self.mqtt and self.mqtt.connected:
                try:
                    self.mqtt.publish("telemetry", self.telemetry())
                except Exception as e:  # noqa: BLE001
                    log.warning("telemetry publish failed: %s", e)
            self._stop.wait(period)

    # =============================================================== commands
    def _on_command(self, msg: dict):
        cmd_id = msg.get("id") or f"cmd-{time.time()}"
        action = msg.get("action")
        params = msg.get("params") or {}
        # safety-critical commands are handled immediately on the MQTT thread
        if action in ("estop", "stop"):
            self._ack(cmd_id, action, *self._run(action, params))
            return
        if action in MOTION_ACTIONS and action != "drive":
            self.cancel_motion.set()  # pre-empt the current motion
        self.pool.submit(lambda: self._ack(cmd_id, action, *self._run(action, params)))

    def _ack(self, cmd_id, action, status, result, error=None):
        if self.mqtt:
            self.mqtt.publish("acks", {"type": "ack", "id": cmd_id, "action": action, "status": status,
                                       "result": result, "error": error, "ts": time.time()}, qos=1)

    def _run(self, action: str, params: dict):
        handler = getattr(self, f"cmd_{action}", None)
        if handler is None:
            return "error", {}, f"unknown action '{action}'"
        try:
            return "ok", handler(**params) or {}, None
        except CommandError as e:
            return e.status, e.result, e.message
        except TypeError as e:
            return "error", {}, f"bad parameters for {action}: {e}"
        except PermissionError as e:
            return "rejected", {}, str(e)
        except Exception as e:  # noqa: BLE001
            log.exception("command %s failed", action)
            return "error", {}, str(e)

    def run_command(self, action: str, **params) -> dict:
        """Synchronous helper used by tests and local tools."""
        status, result, error = self._run(action, params)
        return {"status": status, "result": result, "error": error}

    # ---------------------------------------------------------------- helpers
    def _require_motion(self):
        if not self.state.can_move():
            raise CommandError("rejected", f"robot is in {self.state.state.value}")

    def _power(self, frac: float) -> float:
        return max(float(self.mcfg.get("min_power", 0.25)), min(1.0, frac))

    def _drive_straight(self, distance_m: float, speed: float, cancel: threading.Event) -> dict:
        sign = 1.0 if distance_m >= 0 else -1.0
        dist = abs(distance_m)
        start = self.sensors.distance
        target_heading = self.sensors.heading
        max_speed = float(self.mcfg.get("max_speed_mps", 0.5))
        timeout = time.monotonic() + dist / max(0.05, speed * max_speed) * 2.5 + 3.0
        kp = float(self.mcfg.get("heading_kp", 0.02))
        status = "ok"
        while True:
            traveled = abs(self.sensors.distance - start)
            remaining = dist - traveled
            if remaining <= 0.01:
                break
            if cancel.is_set():
                status = "cancelled"
                break
            if not self.state.can_move():
                status = "rejected"
                break
            if sign > 0 and self.safety.blocked:
                status = "blocked"
                break
            if time.monotonic() > timeout:
                status = "timeout"
                break
            sp = self._power(speed * min(1.0, max(0.4, remaining / 0.25)))
            err = angle_diff(target_heading, self.sensors.heading)
            corr = max(-0.3, min(0.3, kp * err))
            self.motors.set_speed(sign * sp - corr, sign * sp + corr)
            time.sleep(0.02)
        self.motors.stop()
        time.sleep(0.05)
        return {"status": status, "traveled_m": round(abs(self.sensors.distance - start), 3)}

    def _turn(self, angle_deg: float, cancel: threading.Event) -> dict:
        target = self.sensors.heading + angle_deg
        turn_speed = float(self.mcfg.get("turn_speed", 0.5))
        timeout = time.monotonic() + abs(angle_deg) / 30.0 + 4.0
        status = "ok"
        while True:
            err = angle_diff(target, self.sensors.heading)
            if abs(err) < 2.0:
                break
            if cancel.is_set():
                status = "cancelled"
                break
            if not self.state.can_move():
                status = "rejected"
                break
            if time.monotonic() > timeout:
                status = "timeout"
                break
            sp = self._power(turn_speed * min(1.0, abs(err) / 45.0))
            d = 1.0 if err > 0 else -1.0
            self.motors.set_speed(-d * sp, d * sp)
            time.sleep(0.02)
        self.motors.stop()
        time.sleep(0.05)
        return {"status": status, "heading_deg": round(self.sensors.heading, 1)}

    def _begin_motion(self) -> threading.Event:
        self._require_motion()
        if not self.motion_lock.acquire(timeout=3):
            raise CommandError("rejected", "another motion is still running")
        self.cancel_motion = threading.Event()
        return self.cancel_motion

    def _end_motion(self):
        if self.state.state == State.AUTONOMOUS_PATROL:
            self.state.transition(State.IDLE, "motion finished")
        self.motion_lock.release()

    # ---------------------------------------------------------------- motion
    def cmd_drive(self, left: float = 0.0, right: float = 0.0):
        self._reset_virtual_pan()
        self._require_motion()
        if self.state.state == State.AUTONOMOUS_PATROL:
            # the operator grabbed the controls: manual take-over cancels the running mission
            self.cancel_motion.set()
            self._publish_event("manual_takeover", {})
        self.state.transition(State.MANUAL, "tele-op")
        self.last_drive_cmd = time.monotonic()
        l, r = self.motors.set_speed(left, right)
        return {"applied": {"left": l, "right": r}, "blocked": self.safety.blocked}

    def cmd_move(self, distance_m: float, speed: float | None = None):
        cancel = self._begin_motion()
        try:
            self.state.transition(State.AUTONOMOUS_PATROL, "move")
            r = self._drive_straight(float(distance_m), float(speed or self.mcfg.get("default_speed", 0.6)), cancel)
            r["pose"] = self.sensors.pose()
            if r["status"] != "ok":
                raise CommandError(r["status"], f"move {r['status']} after {r['traveled_m']} m", r)
            return r
        finally:
            self._end_motion()

    def cmd_turn(self, angle_deg: float):
        cancel = self._begin_motion()
        try:
            self.state.transition(State.AUTONOMOUS_PATROL, "turn")
            r = self._turn(float(angle_deg), cancel)
            if r["status"] != "ok":
                raise CommandError(r["status"], f"turn {r['status']}", r)
            return r
        finally:
            self._end_motion()

    def _avoid(self, cancel) -> bool:
        """Reactive side-step around an obstacle ahead. Returns True if it made progress.

        back up a little -> turn 90 deg to the freer side -> slide 0.5 m -> turn back ->
        drive 0.8 m past the obstacle; the caller then re-aims at the goal.
        """
        d = self.safety.distances
        side = 1.0 if d.get("left", 0) >= d.get("right", 0) else -1.0
        self._drive_straight(-0.2, 0.5, cancel)
        for s in (side, -side):
            self._turn(90.0 * s, cancel)
            r = self._drive_straight(0.5, 0.5, cancel)
            self._turn(-90.0 * s, cancel)
            if r["status"] == "ok":
                self._drive_straight(0.8, 0.5, cancel)
                return True
            if cancel.is_set():
                return False
            # first side was blocked too: come back to the original line and try the other side
            self._turn(-90.0 * s, cancel)
            self._drive_straight(r["traveled_m"], 0.5, cancel)
            self._turn(90.0 * s, cancel)
        return False

    def _navigate(self, tx: float, ty: float, label: str, cancel) -> dict:
        """Dead-reckoning legs toward (tx, ty) with reactive obstacle avoidance."""
        attempts = 0
        max_attempts = int(self.mcfg.get("avoid_max_attempts", 3))
        speed = float(self.mcfg.get("default_speed", 0.6))
        for _legs in range(12):
            p = self.sensors.pose()
            dx, dy = tx - p["x"], ty - p["y"]
            dist = math.hypot(dx, dy)
            if dist < 0.15:
                break
            bearing = math.degrees(math.atan2(dy, dx))
            t = self._turn(angle_diff(bearing, self.sensors.heading), cancel)
            if t["status"] in ("cancelled", "rejected"):
                raise CommandError(t["status"], f"going to {label}: {t['status']}")
            r = self._drive_straight(dist, speed, cancel)
            if r["status"] == "ok":
                continue
            if r["status"] == "blocked" and attempts < max_attempts:
                attempts += 1
                self._publish_event("avoiding_obstacle", {"zone": label, "attempt": attempts,
                                                          "distances_cm": self.safety.distances})
                if self._avoid(cancel):
                    continue
            raise CommandError(r["status"], f"could not reach {label}: {r['status']}", {"pose": self.sensors.pose()})
        return {"avoidance_attempts": attempts}

    def cmd_go_to_zone(self, zone: str):
        self._reset_virtual_pan()
        if zone not in self.zones:
            raise CommandError("error", f"unknown zone '{zone}'. Known: {list(self.zones)}")
        cancel = self._begin_motion()
        try:
            self.state.transition(State.AUTONOMOUS_PATROL, f"go_to_zone {zone}")
            r = self._navigate(float(self.zones[zone]["x"]), float(self.zones[zone]["y"]), zone, cancel)
            vh = self.zones[zone].get("view_heading")
            if vh is not None:                       # turn to face the room's equipment / front wall
                self._turn(angle_diff(float(vh), self.sensors.heading), cancel)
            self.env.begin_stop()
            return {"zone": zone, "pose": self.sensors.pose(), **r}
        finally:
            self._end_motion()

    def cmd_go_to_point(self, x: float, y: float, heading_deg: float | None = None):
        self._reset_virtual_pan()
        """Drive to a point in metres from Home (patrol routes), optionally ending facing heading_deg."""
        cancel = self._begin_motion()
        try:
            self.state.transition(State.AUTONOMOUS_PATROL, f"go_to_point {x:.1f},{y:.1f}")
            r = self._navigate(float(x), float(y), f"({float(x):.1f}, {float(y):.1f})", cancel)
            if heading_deg is not None:
                self._turn(angle_diff(float(heading_deg), self.sensors.heading), cancel)
            return {"pose": self.sensors.pose(), "zone": self.current_zone(), **r}
        finally:
            self._end_motion()

    def cmd_set_home(self):
        self._reset_virtual_pan()
        self.sensors.reset_pose()
        return {"pose": self.sensors.pose()}

    def cmd_stop(self):
        self.cancel_motion.set()
        self.motors.stop()
        if self.state.state in (State.MANUAL, State.AUTONOMOUS_PATROL):
            self.state.transition(State.IDLE, "stop command")
        return {"state": self.state.state.value}

    def cmd_estop(self):
        self.cancel_motion.set()
        self.motors.hold = True
        self.motors.brake()
        self.state.transition(State.EMERGENCY_STOP, "emergency stop command")
        self.hw.speaker.beep("alarm")
        return {"state": self.state.state.value}

    def cmd_reset(self):
        if self.state.state == State.EMERGENCY_STOP:
            self.motors.hold = self.safety.safe_hold
            self.state.transition(State.IDLE, "reset")
        return {"state": self.state.state.value}

    def cmd_pan_tilt(self, pan: float = 0.0, tilt: float = 0.0):
        if self.hw.extra.get("fixed_camera"):
            return self._virtual_pan(float(pan))
        self.motors.set_pan_tilt(pan, tilt)
        time.sleep(0.3)  # let servos settle before a snapshot
        return {"pan": self.motors.pan, "tilt": self.motors.tilt}

    def _virtual_pan(self, pan: float):
        """Budget build without pan/tilt servos: 'look' at an angle by turning the whole robot. The pan offset is
        remembered, so pan 0 turns it back (the server's look-around and approach logic works unchanged)."""
        target = max(-90.0, min(90.0, pan))
        delta = target - self.motors.pan
        if abs(delta) >= 2.0:
            cancel = self._begin_motion()
            try:
                self.state.transition(State.AUTONOMOUS_PATROL, "look around (fixed camera)")
                r = self._turn(delta, cancel)
                if r["status"] != "ok":
                    raise CommandError(r["status"], f"turn {r['status']}", r)
            finally:
                self._end_motion()
        self.motors.pan, self.motors.tilt = target, 0.0
        time.sleep(0.2)
        return {"pan": target, "tilt": 0.0, "fixed_camera": True}

    def _reset_virtual_pan(self):
        if self.hw.extra.get("fixed_camera"):
            self.motors.pan = 0.0

    # ---------------------------------------------------------------- virtual wiring (simulated robot only)
    def _harness(self):
        h = self.hw.extra.get("harness")
        if h is None:
            raise CommandError("rejected", "virtual wiring only works on the simulated robot (2D or Webots)")
        return h

    def cmd_set_wiring(self, enabled: bool = True, wires: dict | None = None):
        """Apply the wires made on the Wiring Bench: parts work only if wired correctly."""
        self.motors.stop()
        st = self._harness().set(enabled, wires)
        log.info("Virtual wiring %s: %d/%d wires correct, drivable=%s", "ON" if st["enabled"] else "OFF",
                 st["done"], st["total"], st["drivable"])
        return st

    def cmd_wiring_status(self):
        return self._harness().status()

    def cmd_wiring_spec(self):
        from .wiring_spec import SPEC

        return SPEC

    # ---------------------------------------------------------------- sensing
    def cmd_snapshot(self, size: int | None = None):
        snap = self.camera.snapshot(size)
        snap["zone"] = self.current_zone()
        snap["pose"] = self.sensors.pose()
        snap["pan_tilt"] = {"pan": self.motors.pan, "tilt": self.motors.tilt}
        return snap

    def cmd_read_environment(self, fresh: bool = False, occupied: bool | None = None):
        if fresh:
            self.env.begin_stop()
        r = self.env.read_settled(occupied=occupied)
        if not r:
            raise CommandError("error", "climate sensor (AHT20 / BME680) has no reading - see Robot health")
        r["zone"] = self.current_zone()
        return r

    def cmd_listen_audio(self, seconds: float | None = None):
        r = self.audio.listen(seconds)
        r["zone"] = self.current_zone()
        return r

    def cmd_sound_scan(self, step_deg: float = 45.0, seconds: float = 0.8):
        """Find where a sound comes from with the front-facing (directional) microphone.

        Turns a full circle in steps, listening at each heading, then faces the loudest one.
        """
        cancel = self._begin_motion()
        try:
            self.state.transition(State.AUTONOMOUS_PATROL, "sound scan")
            step = max(20.0, min(120.0, float(step_deg)))
            readings = []
            for _ in range(int(round(360.0 / step))):
                if cancel.is_set():
                    raise CommandError("cancelled", "sound scan cancelled")
                a = self.audio.listen(float(seconds))
                readings.append({"heading_deg": round(self.sensors.heading, 1), "db": a["db"], "label": a["label"],
                                 "voice_like": a.get("voice_like", False)})
                self._turn(step, cancel)
            voiced = [r for r in readings if r["voice_like"]] or readings
            best = max(voiced, key=lambda r: r["db"])
            spread = round(max(r["db"] for r in readings) - min(r["db"] for r in readings), 1)
            # refine between steps: fit a parabola through the loudest reading and its two neighbours
            i = readings.index(best)
            lo, hi = readings[i - 1]["db"], readings[(i + 1) % len(readings)]["db"]
            den = lo - 2 * best["db"] + hi
            frac = 0.5 * (lo - hi) / den if den < -1e-6 else 0.0
            target = best["heading_deg"] + max(-0.5, min(0.5, frac)) * step
            self._turn(angle_diff(target, self.sensors.heading), cancel)
            best = {**best, "heading_deg": round(((target + 180) % 360) - 180, 1)}
            return {"readings": readings, "best_heading_deg": best["heading_deg"], "best_db": best["db"],
                    "label": best["label"], "voice_like": best["voice_like"], "spread_db": spread,
                    "directional_mic": bool(self.cfg.get("audio", {}).get("directional_mic", True)),
                    "front_cm": self.safety.distances.get("center")}
        finally:
            self._end_motion()

    def cmd_speak(self, text: str):
        self.hw.speaker.say(str(text)[:300])
        return {"spoken": True}

    def cmd_set_privacy(self, enabled: bool):
        self.camera.privacy = bool(enabled)
        if enabled:
            asyncio.run_coroutine_threadsafe(self.camera.close_webrtc(), self.loop)
        self._publish_event("privacy_mode", {"enabled": self.camera.privacy})
        return {"privacy_mode": self.camera.privacy}

    def cmd_webrtc_offer(self, sdp: str, type: str = "offer"):  # noqa: A002 - matches SDP field name
        fut = asyncio.run_coroutine_threadsafe(self.camera.handle_webrtc_offer(sdp, type), self.loop)
        return fut.result(timeout=15)

    def cmd_recheck_hardware(self):
        """Look for the parts again (after plugging something in): restarts the robot program in ~1 s.
        In simulation there is nothing to re-detect, so it just reports the current part health."""
        if self.hw.simulated:
            return {"restarting": False, "health": self.hw.health, "faults": self.hw.faults()}
        threading.Timer(0.8, self._restart_process).start()
        return {"restarting": True, "faults_before": self.hw.faults()}

    def _restart_process(self):
        import os
        import sys

        log.warning("Restarting the robot program to detect the hardware again")
        try:
            self.shutdown()
        except Exception:  # noqa: BLE001
            log.exception("shutdown before restart failed")
        os.execv(sys.executable, [sys.executable, "-m", "robot.main", *sys.argv[1:]])

    def cmd_ping(self, **_):
        return {"robot_ts": time.time()}

    def cmd_status(self):
        return self.telemetry()
