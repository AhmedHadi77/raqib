"""Webots hardware: the Raqib software drives the 3D robot in webots/worlds/raqib_campus.wbt.

Real 3D physics and sensors from Webots:
  wheels (motors + wheel encoders), 3 sonar sensors (HC-SR04 beam), IMU (yaw + gyro),
  pan/tilt camera on a 1 m mast (real rendered images), speaker (spoken warnings).
Still modelled in software, because Webots has no such sensors:
  BME680 / MQ-135 climate + gas readings and the microphone (same per-room models as the
  built-in simulator, using the robot's true position in Webots).
The robot's controller also animates the exam students (head turns, phone, cheat sheet, earpiece)
on the same timetable the backend's proctoring checks expect.

Start Webots with the world first, then this program (start_robot_webots.bat does both).
"""
from __future__ import annotations

import logging
import math
import os
import queue
import random
import sys
import threading
import time

import numpy as np

from ..config import load_sim_world
from .base import Battery, Encoders, Hardware, Imu, ImuReading, Motors, PanTilt, Speaker, Ultrasonics
from .sim import (SIM_GAS_BASELINE_OHM, SimBattery, SimCamera, SimEnv, SimMicrophone, SimWorld)

log = logging.getLogger(__name__)

WEBOTS_HOMES = [r"C:\Program Files\Webots", r"C:\Program Files (x86)\Webots",
                os.path.expanduser(r"~\AppData\Local\Programs\Webots"), "/usr/local/webots", "/opt/webots",
                "/snap/webots/current/usr/share/webots", "/Applications/Webots.app/Contents"]


def import_webots_controller(home: str | None = None):
    """Make Webots' Python controller library importable from this (normal) Python."""
    home = home or os.environ.get("WEBOTS_HOME")
    if not home or not os.path.isdir(home):
        home = next((h for h in WEBOTS_HOMES if os.path.isdir(os.path.join(h, "lib", "controller"))), None)
    if not home:
        raise RuntimeError("Webots not found. Install Webots R2025a or set WEBOTS_HOME to its folder.")
    os.environ["WEBOTS_HOME"] = home
    sys.path.insert(0, os.path.join(home, "lib", "controller", "python"))
    if sys.platform == "win32":
        for d in (os.path.join(home, "lib", "controller"), os.path.join(home, "msys64", "mingw64", "bin"),
                  os.path.join(home, "msys64", "mingw64", "bin", "cpp")):
            if os.path.isdir(d):
                os.add_dll_directory(d)
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    elif sys.platform.startswith("linux"):
        lib = os.path.join(home, "lib", "controller")
        os.environ["LD_LIBRARY_PATH"] = lib + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")
    import controller  # noqa: F401  (Webots' module)

    return controller, home


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _axis_angle(R) -> list[float]:
    ang = math.acos(max(-1.0, min(1.0, (np.trace(R) - 1) / 2)))
    if ang < 1e-9:
        return [0.0, 0.0, 1.0, 0.0]
    ax = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2 * math.sin(ang))
    return [float(ax[0]), float(ax[1]), float(ax[2]), ang]


class WebotsWorld(SimWorld):
    """Same shared state as the 2D simulator, but filled in by Webots every simulation step."""

    def __init__(self, cfg: dict, world: dict):
        super().__init__(cfg, world, start=False)
        # the 3D students sit 0.33 m behind the desk point in sim_world.yaml (see webots/build_world.py)
        self.students = [{**st, "x": float(st["x"]) - 0.33} for st in self.students]
        self.pan_actual = self.tilt_actual = 0.0
        self.partitions = sorted(float(v) for v in (cfg.get("webots", {}) or {}).get("partitions", [1.5, 4.5, 7.0, 10.5]))
        wcfg = cfg.get("webots", {}) or {}
        self.wheel_radius = float(cfg.get("motion", {}).get("wheel_diameter_m", 0.065)) / 2
        self.sonar = {"left": 400.0, "center": 400.0, "right": 400.0}
        self.imu_yaw = 0.0
        self.frame: np.ndarray | None = None
        self.frame_t = 0.0
        self.say_q: queue.Queue[str] = queue.Queue()
        self.connected = threading.Event()
        self.error: str | None = None
        self.sim_time = 0.0
        self._home = wcfg.get("home")
        self._camera_ms = int(wcfg.get("camera_period_ms", 64))
        self._thread = threading.Thread(target=self._run_webots, name="webots", daemon=True)
        self._thread.start()
        if not self.connected.wait(float(wcfg.get("connect_timeout_s", 120))) or self.error:
            raise RuntimeError(self.error or "Webots did not answer. Open webots/worlds/raqib_campus.wbt in Webots first.")

    # ------------------------------------------------------------------ the Webots thread
    def _run_webots(self):
        try:
            controller, home = import_webots_controller(self._home)
            os.environ.setdefault("WEBOTS_CONTROLLER_URL", "raqib")
            log.info("Connecting to Webots (%s) ...", home)
            sup = controller.Supervisor()
        except Exception as e:  # noqa: BLE001
            self.error = f"Could not start the Webots controller: {e}"
            log.error(self.error)
            self.connected.set()
            return
        ts = int(sup.getBasicTimeStep())
        step = max(ts, 16)
        dev = sup.getDevice
        lm, rm = dev("left wheel motor"), dev("right wheel motor")
        for m in (lm, rm):
            m.setPosition(float("inf"))
            m.setVelocity(0.0)
        lps, rps = dev("left wheel sensor"), dev("right wheel sensor")
        sonars = {"left": dev("us_left"), "center": dev("us_center"), "right": dev("us_right")}
        imu, gyro, cam = dev("imu"), dev("gyro"), dev("camera")
        pan_m, tilt_m = dev("pan motor"), dev("tilt motor")
        pan_s, tilt_s = dev("pan sensor"), dev("tilt sensor")
        for d in (pan_s, tilt_s):
            if d is not None:
                d.enable(step)
        speaker = dev("speaker")
        for d in (lps, rps, imu, gyro, *sonars.values()):
            d.enable(step)
        cam.enable(self._camera_ms)
        try:
            speaker.setEngine("pico")
            speaker.setLanguage("en-US")
        except Exception:  # noqa: BLE001
            pass
        me = sup.getSelf()
        heads = {}
        for st in self.students:
            n = st["name"]
            nodes = {k: sup.getFromDef(f"{k}_{n}") for k in ("HEAD", "PHONE", "NOTES", "EAR")}
            if nodes["HEAD"] is not None:
                heads[n] = ({k: (v.getField("rotation") if k == "HEAD" else v.getField("scale")) for k, v in nodes.items()
                             if v is not None}, {})
        W, H = cam.getWidth(), cam.getHeight()
        last_l = last_r = None
        last_pan = last_tilt = None
        k = 0
        self.connected.set()
        log.info("Webots connected: %d students animated, camera %dx%d", len(heads), W, H)
        vmax = self.max_speed / self.wheel_radius
        while sup.step(step) != -1:
            k += 1
            with self.lock:
                cl, cr, pan, tilt = self.cmd_l, self.cmd_r, self.pan, self.tilt
            lm.setVelocity(max(-lm.getMaxVelocity(), min(lm.getMaxVelocity(), cl * vmax)))
            rm.setVelocity(max(-rm.getMaxVelocity(), min(rm.getMaxVelocity(), cr * vmax)))
            if pan != last_pan or tilt != last_tilt:
                pan_m.setPosition(math.radians(pan))
                tilt_m.setPosition(-math.radians(tilt))          # Webots: +y rotation looks down
                last_pan, last_tilt = pan, tilt
            pl, pr = lps.getValue(), rps.getValue()
            pos = me.getPosition()
            R = me.getOrientation()
            yaw = imu.getRollPitchYaw()[2]
            gz = gyro.getValues()[2]
            with self.lock:
                if last_l is not None and not math.isnan(pl):
                    self.dist_l += abs(pl - last_l) * self.wheel_radius
                    self.dist_r += abs(pr - last_r) * self.wheel_radius
                self.x, self.y = float(pos[0]), float(pos[1])
                self.theta = math.atan2(R[3], R[0])
                self.imu_yaw = yaw
                if pan_s is not None:
                    self.pan_actual = math.degrees(pan_s.getValue())
                    self.tilt_actual = -math.degrees(tilt_s.getValue())
                self.gyro_z = math.degrees(gz)
                for name, d in sonars.items():
                    self.sonar[name] = float(d.getValue())
                drain = 0.0004 + 0.002 * (abs(cl) + abs(cr))
                self.battery_pct = max(0.0, self.battery_pct - drain * step / 1000)
                self.sim_time = sup.getTime()
            last_l, last_r = pl, pr
            if k % max(1, self._camera_ms // step) == 0:
                raw = cam.getImage()
                if raw:
                    img = np.frombuffer(raw, np.uint8).reshape((H, W, 4))[:, :, :3].copy()   # BGRA -> BGR
                    with self.lock:
                        self.frame, self.frame_t = img, time.time()
            if k % 6 == 0:
                self._animate(heads)
            while not self.say_q.empty():
                text = self.say_q.get_nowait()
                try:
                    speaker.speak(text, 1.0)
                except Exception as e:  # noqa: BLE001
                    log.debug("speaker: %s", e)
        self.error = "Webots was closed or the world was reset"
        log.error("%s - stopping the robot program.", self.error)
        os._exit(3)

    def room_index(self, x: float) -> int:
        """Which room an x position is in (rooms are separated by the partition walls)."""
        return sum(1 for p in self.partitions if x >= p)

    def visible_students(self, pan_deg: float, hfov_deg: float = 62.2) -> list[dict]:
        """Students in the camera's view and in the same room (walls block the view)."""
        with self.lock:
            x, y, th = self.x, self.y, self.theta
        room = self.room_index(x)
        cam = th + math.radians(pan_deg)
        out = []
        for st in self.students:
            if self.room_index(float(st["x"])) != room:
                continue
            dx, dy = float(st["x"]) - x, float(st["y"]) - y
            d = math.hypot(dx, dy)
            rel = math.degrees((math.atan2(dy, dx) - cam + math.pi) % (2 * math.pi) - math.pi)
            if abs(rel) > hfov_deg / 2 or d > 7.0:
                continue
            ss = self.student_state(st)
            ss.update({"distance_m": round(d, 2), "bearing_deg": round(rel, 1), "x_img": round(0.5 - rel / hfov_deg, 3)})
            out.append(ss)
        return sorted(out, key=lambda r: r["x_img"])

    def _animate(self, heads: dict):
        """Pose each student for what they are doing right now (same timetable as the proctor checks)."""
        for st in self.students:
            entry = heads.get(st["name"])
            if not entry:
                continue
            fields, last = entry
            s = self.student_state(st)
            key = (round(s["yaw"]), round(s["pitch"]), tuple(sorted(s["objects"])))
            if last.get("key") == key:
                continue
            last["key"] = key
            R = _rz(math.radians(s["yaw"])) @ _ry(math.radians(-s["pitch"]))
            fields["HEAD"].setSFRotation(_axis_angle(R))
            for obj, part in (("cell phone", "PHONE"), ("notes", "NOTES"), ("earpiece", "EAR")):
                if part in fields:
                    v = 1.0 if obj in s["objects"] else 0.001
                    fields[part].setSFVec3f([v, v, v])


# ======================================================================= parts
class WebotsMotors(Motors):
    def __init__(self, w: WebotsWorld):
        self.w = w

    def set_wheels(self, left: float, right: float) -> None:
        with self.w.lock:
            self.w.cmd_l = max(-1.0, min(1.0, float(left)))
            self.w.cmd_r = max(-1.0, min(1.0, float(right)))


class WebotsPanTilt(PanTilt):
    def __init__(self, w: WebotsWorld):
        self.w = w

    def set_angles(self, pan_deg: float, tilt_deg: float) -> None:
        with self.w.lock:
            self.w.pan = max(-90.0, min(90.0, float(pan_deg)))
            self.w.tilt = max(-45.0, min(60.0, float(tilt_deg)))


class WebotsUltrasonics(Ultrasonics):
    def __init__(self, w: WebotsWorld):
        self.w = w

    def read_cm(self) -> dict[str, float]:
        with self.w.lock:
            s = dict(self.w.sonar)
        return {k: round(max(2.0, min(400.0, v + random.gauss(0, 0.3))), 1) for k, v in s.items()}


class WebotsEncoders(Encoders):
    def __init__(self, w: WebotsWorld):
        self.w = w

    def ticks(self) -> tuple[int, int]:
        with self.w.lock:
            return int(self.w.dist_l * self.w.ticks_per_m), int(self.w.dist_r * self.w.ticks_per_m)


class WebotsImu(Imu):
    def __init__(self, w: WebotsWorld):
        self.w = w

    def read(self) -> ImuReading:
        with self.w.lock:
            return ImuReading(yaw_deg=math.degrees(self.w.imu_yaw), gyro_z_dps=self.w.gyro_z)


class WebotsCamera(SimCamera):
    """Real rendered pictures from the Webots camera; ground truth for the free mock vision."""

    def capture(self) -> np.ndarray:
        # like a real pan/tilt: wait until the servos reach the commanded angle, then take a fresh frame
        t0 = time.time()
        while time.time() - t0 < 2.0:
            with self.w.lock:
                settled = abs(self.w.pan_actual - self.w.pan) < 1.5 and abs(self.w.tilt_actual - self.w.tilt) < 1.5
            if settled:
                break
            time.sleep(0.03)
        t_settled = time.time()
        while time.time() - t_settled < 0.5:
            with self.w.lock:
                if self.w.frame is not None and self.w.frame_t > t_settled:
                    break
            time.sleep(0.02)
        with self.w.lock:
            f = self.w.frame
            pan_now = self.w.pan_actual
        if f is None:
            return super().capture()
        # what this exact frame shows (students in view at the camera's real angle), for the free mock vision
        self._frame_students = self.w.visible_students(pan_now, self.hfov)
        return f.copy()

    def scene_truth(self) -> dict | None:
        t = super().scene_truth() or {}
        t["webots"] = True
        if getattr(self, "_frame_students", None) is not None:
            t["students"] = self._frame_students
        with self.w.lock:
            t["true_pose"] = {"x": round(self.w.x, 3), "y": round(self.w.y, 3), "heading_deg": round(math.degrees(self.w.theta), 1)}
            t["camera_state"] = {"pan_actual": round(self.w.pan_actual, 1), "tilt_actual": round(self.w.tilt_actual, 1),
                                 "frame_age_s": round(time.time() - self.w.frame_t, 2), "sim_time": round(self.w.sim_time, 1)}
        return t


class WebotsSpeaker(Speaker):
    def __init__(self, w: WebotsWorld):
        self.w = w

    def say(self, text: str) -> None:
        log.info("[SPEAKER] %s", text)
        self.w.say_q.put(text)

    def beep(self, kind: str = "info") -> None:
        log.info("[SPEAKER] beep (%s)", kind)


def create_webots_hardware(cfg: dict) -> Hardware:
    world = load_sim_world(cfg.get("sim_world_path"))
    w = WebotsWorld(cfg, world)
    hw = Hardware(
        motors=WebotsMotors(w),
        pan_tilt=WebotsPanTilt(w),
        ultrasonics=WebotsUltrasonics(w),
        encoders=WebotsEncoders(w),
        imu=WebotsImu(w),
        env=SimEnv(w, cfg),
        camera=WebotsCamera(w, cfg),
        microphone=SimMicrophone(w),
        speaker=WebotsSpeaker(w),
        battery=SimBattery(w, int(cfg.get("hardware", {}).get("battery_cells", 3))),
        simulated=True,
        health={**{k: {"ok": True, "detail": "Webots", "hint": ""} for k in
                   ("motors", "pan_tilt", "ultrasonic", "encoders", "imu", "camera", "speaker")},
                **{k: {"ok": True, "detail": "simulated (Webots has no such sensor)", "hint": ""} for k in
                   ("environment", "microphone", "battery")}},
        extra={"world": w, "gas_baseline_ohm": SIM_GAS_BASELINE_OHM, "webots": True},
    )
    return hw


__all__ = ["create_webots_hardware", "import_webots_controller", "Battery"]
