"""Simulated hardware - a small 2D physics world so the whole stack runs without a robot.

The simulated robot drives around `sim_world.yaml`: it has wheels, encoders, an IMU,
three ultrasonic sensors that ray-cast against walls/obstacles, a climate sensor + MQ-135 that
reports each room's climate, a camera that renders a synthetic picture of the room and
a microphone that synthesises the room's sound signature.

`sim_build` picks which robot is simulated:
  esp32 (default)  - the ESP32 robot 3.0: 2WD + caster, one HC-SR04P at the front, MPU6050, AHT20 + BMP280,
                     XIAO ESP32S3 Sense camera + microphone, no speaker (the phone speaks), PC is the brain
  budget           - the Raspberry Pi RM 500 build: 4WD, fixed USB webcam (the robot turns to look), AHT20 + BMP280,
                     no gas sensor, no wheel encoders (distance from motor time + IMU), Pi on a power bank
  full             - PCA9685 + pan/tilt servos, BME680 with VOC, 3-cell UPS module
"""
from __future__ import annotations

import logging
import math
import os
import random
import threading
import time

import numpy as np

from .. import imaging as im
from ..config import load_sim_world
from .base import (
    Battery, BatteryReading, Camera, Encoders, EnvRaw, EnvSensor, Hardware, Imu, ImuReading,
    Microphone, Motors, PanTilt, Speaker, Ultrasonics,
)

log = logging.getLogger(__name__)

ROBOT_RADIUS_M = 0.13
SENSOR_FORWARD_OFFSET_M = 0.12
SIM_GAS_BASELINE_OHM = 50_000.0
VOC_GAS_RATIO = {"low": 0.98, "medium": 0.85, "high": 0.70, "extreme": 0.15}
VOC_MQ135_PPM = {"low": 450.0, "medium": 800.0, "high": 1300.0, "extreme": 2500.0}
MQ135_A, MQ135_B = 116.6020682, -2.769034857


def _ray_box(ox, oy, dx, dy, box) -> float | None:
    """Ray vs axis-aligned box (slab method). Returns distance or None."""
    x0, y0, x1, y1 = box
    tmin, tmax = -math.inf, math.inf
    for o, d, lo, hi in ((ox, dx, x0, x1), (oy, dy, y0, y1)):
        if abs(d) < 1e-12:
            if o < lo or o > hi:
                return None
        else:
            t1, t2 = (lo - o) / d, (hi - o) / d
            if t1 > t2:
                t1, t2 = t2, t1
            tmin, tmax = max(tmin, t1), min(tmax, t2)
            if tmin > tmax:
                return None
    if tmax < 0:
        return None
    return tmin if tmin >= 0 else 0.0


def _ray_walls(ox, oy, dx, dy, bounds) -> float:
    """Distance from a point inside the bounds to the surrounding walls along a ray."""
    x0, y0, x1, y1 = bounds
    ts = []
    if dx > 1e-12:
        ts.append((x1 - ox) / dx)
    elif dx < -1e-12:
        ts.append((x0 - ox) / dx)
    if dy > 1e-12:
        ts.append((y1 - oy) / dy)
    elif dy < -1e-12:
        ts.append((y0 - oy) / dy)
    ts = [t for t in ts if t >= 0]
    return min(ts) if ts else 4.0


class SimWorld:
    """Shared simulation state + 100 Hz physics thread."""

    def __init__(self, cfg: dict, world: dict, start: bool = True):
        self.cfg = cfg
        self.world = world
        m = cfg.get("motion", {})
        self.max_speed = float(m.get("max_speed_mps", 0.5))
        self.wheel_base = float(m.get("wheel_base_m", 0.15))
        self.ticks_per_m = float(m.get("encoder_ticks_per_rev", 20)) / (math.pi * float(m.get("wheel_diameter_m", 0.065)))
        self.bounds = world.get("bounds", [-1, -2, 11, 2])
        self.obstacles = [list(map(float, b)) for b in world.get("obstacles", [])]
        self.scenarios = world.get("scenarios", {})
        self.zones = cfg.get("zones", {})
        self.sources = world.get("sound_sources", []) or []
        self.students = world.get("students", []) or []
        self.directional_mic = bool(cfg.get("audio", {}).get("directional_mic", True))
        self.t0 = time.monotonic()

        self.lock = threading.RLock()
        self.x = self.y = self.theta = 0.0
        self.cmd_l = self.cmd_r = 0.0
        self.dist_l = self.dist_r = 0.0
        self.gyro_z = 0.0
        self.pan = self.tilt = 0.0
        self.battery_pct = 100.0
        self.collisions = 0
        self._stop = threading.Event()
        if start:                                    # Webots runs its own physics instead (hal/webots.py)
            self._thread = threading.Thread(target=self._run, name="sim-physics", daemon=True)
            self._thread.start()

    # ---------------------------------------------------------------- physics
    def _collides(self, x: float, y: float) -> bool:
        x0, y0, x1, y1 = self.bounds
        r = ROBOT_RADIUS_M
        if x - r < x0 or x + r > x1 or y - r < y0 or y + r > y1:
            return True
        for bx0, by0, bx1, by1 in self.obstacles:
            cx, cy = min(max(x, bx0), bx1), min(max(y, by0), by1)
            if (x - cx) ** 2 + (y - cy) ** 2 < r * r:
                return True
        return False

    def _run(self):
        dt = 0.01
        last = time.monotonic()
        while not self._stop.is_set():
            now = time.monotonic()
            dt = min(now - last, 0.05)
            last = now
            with self.lock:
                vl = self.cmd_l * self.max_speed
                vr = self.cmd_r * self.max_speed
                v = (vl + vr) / 2.0
                w = (vr - vl) / self.wheel_base
                nth = self.theta + w * dt
                nx = self.x + v * math.cos(nth) * dt
                ny = self.y + v * math.sin(nth) * dt
                if self._collides(nx, ny):
                    if abs(v) > 1e-3:
                        self.collisions += 1
                    nx, ny = self.x, self.y  # bumper: translation blocked, wheels slip
                self.x, self.y, self.theta = nx, ny, (nth + math.pi) % (2 * math.pi) - math.pi
                self.gyro_z = math.degrees(w)
                self.dist_l += abs(vl) * dt
                self.dist_r += abs(vr) * dt
                drain = 0.0004 + 0.002 * (abs(self.cmd_l) + abs(self.cmd_r))
                self.battery_pct = max(0.0, self.battery_pct - drain * dt)
            time.sleep(0.01)

    def stop(self):
        self._stop.set()

    # ---------------------------------------------------------------- queries
    def ray(self, angle_offset_rad: float) -> float:
        with self.lock:
            ox = self.x + SENSOR_FORWARD_OFFSET_M * math.cos(self.theta)
            oy = self.y + SENSOR_FORWARD_OFFSET_M * math.sin(self.theta)
            a = self.theta + angle_offset_rad
        dx, dy = math.cos(a), math.sin(a)
        best = _ray_walls(ox, oy, dx, dy, self.bounds)
        for box in self.obstacles:
            t = _ray_box(ox, oy, dx, dy, box)
            if t is not None:
                best = min(best, t)
        return best

    def zone_at(self, x: float | None = None, y: float | None = None) -> str | None:
        with self.lock:
            x = self.x if x is None else x
            y = self.y if y is None else y
        best, best_d = None, math.inf
        for name, z in self.zones.items():
            d = math.hypot(x - float(z["x"]), y - float(z["y"]))
            if d <= float(z.get("radius", 1.0)) and d < best_d:
                best, best_d = name, d
        return best

    def active_sources(self) -> list[dict]:
        """Talkers speaking right now (their schedule repeats every period)."""
        t = time.monotonic() - self.t0
        out = []
        for src in self.sources:
            period = float(src.get("period_s", 60))
            ph = (t - float(src.get("phase_s", 0))) % period
            if ph < float(src.get("on_s", period)):
                out.append(src)
        return out

    def heard_db(self, src: dict) -> float:
        """Sound level of one talker at the microphone: distance law + front-facing (cardioid) mic."""
        with self.lock:
            x, y, th = self.x, self.y, self.theta
        d = math.hypot(float(src["x"]) - x, float(src["y"]) - y)
        db = float(src.get("level_db", 60)) - 20 * math.log10(max(d, 0.3))
        if self.directional_mic:
            rel = math.atan2(float(src["y"]) - y, float(src["x"]) - x) - th
            g = max(0.5 * (1 + math.cos(rel)), 0.1)
            db += 20 * math.log10(g)
        return db

    def student_state(self, st: dict) -> dict:
        """What one simulated student is doing right now."""
        t = time.monotonic() - self.t0
        yaw, pitch, objects = 0.0, -12.0, []          # writing posture: head slightly down
        for b in st.get("behaviours", []):
            every = float(b.get("every_s", 60))
            if t < float(b.get("at_s", 0)) or (t - float(b.get("at_s", 0))) % every >= float(b.get("for_s", 10)):
                continue
            kind = b.get("type")
            if kind == "head_turn":
                yaw = float(b.get("yaw", 55))
            elif kind == "look_down":
                pitch = -float(b.get("pitch", 50))
            elif kind == "phone":
                objects.append("cell phone")
                pitch = -48.0
            elif kind == "notes":
                objects.append("notes")
                pitch = -30.0
            elif kind == "earpiece":
                objects.append("earpiece")
        return {"name": st["name"], "x": float(st["x"]), "y": float(st["y"]), "yaw": yaw, "pitch": pitch,
                "objects": objects}

    def visible_students(self, pan_deg: float, hfov_deg: float = 62.2) -> list[dict]:
        """Students inside the camera's field of view, in the robot's room, with their image position."""
        with self.lock:
            x, y, th = self.x, self.y, self.theta
        room = self.zone_at(x, y)
        out = []
        cam = th + math.radians(pan_deg)
        for st in self.students:
            if room is None or self.zone_at(float(st["x"]), float(st["y"])) != room:
                continue
            dx, dy = float(st["x"]) - x, float(st["y"]) - y
            d = math.hypot(dx, dy)
            rel = math.degrees((math.atan2(dy, dx) - cam + math.pi) % (2 * math.pi) - math.pi)
            if abs(rel) > hfov_deg / 2 or d > 7.0:
                continue
            ss = self.student_state(st)
            ss.update({"distance_m": round(d, 2), "bearing_deg": round(rel, 1),
                       "x_img": round(0.5 - rel / hfov_deg, 3)})      # 0 = left edge, 1 = right edge
            out.append(ss)
        return sorted(out, key=lambda r: r["x_img"])

    def ahead(self) -> tuple[float, str]:
        """Distance to what is straight ahead and what it is (for 'what do you see')."""
        with self.lock:
            ox, oy, a = self.x, self.y, self.theta
        dx, dy = math.cos(a), math.sin(a)
        best, what = _ray_walls(ox, oy, dx, dy, self.bounds), "wall"
        for box in self.obstacles:
            t = _ray_box(ox, oy, dx, dy, box)
            if t is not None and t < best:
                best, what = t, ("desk with a student" if box[0] > 11 else "chair")
        return best, what

    def scenario(self) -> tuple[str, dict]:
        zone = self.zone_at()
        if zone and zone in self.scenarios:
            return zone, self.scenarios[zone]
        return "Corridor", self.scenarios.get("_corridor", {})


# ======================================================================= parts
class SimMotors(Motors):
    def __init__(self, w: SimWorld):
        self.w = w

    def set_wheels(self, left: float, right: float) -> None:
        with self.w.lock:
            self.w.cmd_l = max(-1.0, min(1.0, float(left)))
            self.w.cmd_r = max(-1.0, min(1.0, float(right)))


class SimPanTilt(PanTilt):
    def __init__(self, w: SimWorld):
        self.w = w

    def set_angles(self, pan_deg: float, tilt_deg: float) -> None:
        with self.w.lock:
            self.w.pan = max(-90.0, min(90.0, pan_deg))
            self.w.tilt = max(-45.0, min(60.0, tilt_deg))


class SimUltrasonics(Ultrasonics):
    def __init__(self, w: SimWorld, front_only: bool = False):
        self.w = w
        self.front_only = front_only        # the ESP32 robot has one sensor, at the front

    def read_cm(self) -> dict[str, float]:
        out = {"left": 400.0, "right": 400.0}
        sensors = (("center", 0.0),) if self.front_only else (("left", math.radians(45)), ("center", 0.0), ("right", math.radians(-45)))
        for name, ang in sensors:
            # HC-SR04 has a ~15 deg beam: cast a small fan of rays and keep the nearest echo
            d = min(self.w.ray(ang + math.radians(o)) for o in (-7.5, -3.75, 0.0, 3.75, 7.5))
            d = d * 100.0 + random.gauss(0, 0.3)
            out[name] = round(max(2.0, min(400.0, d)), 1)
        return out


class SimEncoders(Encoders):
    def __init__(self, w: SimWorld):
        self.w = w

    def ticks(self) -> tuple[int, int]:
        with self.w.lock:
            return int(self.w.dist_l * self.w.ticks_per_m), int(self.w.dist_r * self.w.ticks_per_m)


class SimImu(Imu):
    def __init__(self, w: SimWorld):
        self.w = w

    def read(self) -> ImuReading:
        with self.w.lock:
            yaw = math.degrees(self.w.theta) + random.gauss(0, 0.15)
            gz = self.w.gyro_z + random.gauss(0, 0.2)
        return ImuReading(yaw_deg=yaw, pitch_deg=random.gauss(0, 0.2), roll_deg=random.gauss(0, 0.2),
                          gyro_z_dps=gz, accel_g=(0.0, 0.0, 1.0))


class SimEnv(EnvSensor):
    def __init__(self, w: SimWorld, cfg: dict, voc: bool = True, gas: bool = True):
        self.w = w
        self.gas = gas                                   # False = no MQ-135 fitted
        self.voc = voc                                   # BME680 has a VOC gas resistance, the AHT20 + BMP280 does not
        self.r0 = float(cfg.get("environment", {}).get("mq135_r0", 76.63))
        self.rl = float(cfg.get("hardware", {}).get("mq135_load_resistor_kohm", 10.0))

    def read(self) -> EnvRaw:
        _, sc = self.w.scenario()
        voc = sc.get("voc_level", "low")
        gas = SIM_GAS_BASELINE_OHM * VOC_GAS_RATIO.get(voc, 0.98) * random.uniform(0.985, 1.0)
        ppm = VOC_MQ135_PPM.get(voc, 450.0) * random.uniform(0.95, 1.05)
        rs = self.r0 * (ppm / MQ135_A) ** (1.0 / MQ135_B)
        vout = 5.0 * self.rl / (rs + self.rl)
        return EnvRaw(
            temperature_c=float(sc.get("temperature_c", 25.0)) + random.gauss(0, 0.15),
            humidity_pct=float(sc.get("humidity_pct", 50.0)) + random.gauss(0, 0.6),
            pressure_hpa=1009.0 + random.gauss(0, 0.3),
            gas_resistance_ohm=gas if self.voc else None,
            mq135_volts=vout if self.gas else None,
        )


class SimCamera(Camera):
    def __init__(self, w: SimWorld, cfg: dict):
        self.w = w
        c = cfg.get("camera", {})
        self.W, self.H = int(c.get("width", 640)), int(c.get("height", 480))
        self.hfov = float(c.get("hfov_deg", 62.2))
        self.webcam = None
        src = os.environ.get("ROBOT_SIM_CAMERA") or c.get("sim_source", "render")
        if src == "webcam":
            try:
                import cv2

                cam = cv2.VideoCapture(int(c.get("sim_webcam_index", 0)))
                if cam.isOpened():
                    cam.set(cv2.CAP_PROP_FRAME_WIDTH, self.W)
                    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, self.H)
                    self.webcam = cam
                    log.warning("Simulated robot is using the PC webcam as its camera")
                else:
                    log.warning("No webcam found - using the rendered camera")
            except Exception as e:  # noqa: BLE001
                log.warning("Webcam unavailable (%s) - using the rendered camera", e)

    def scene_truth(self) -> dict | None:
        zone, sc = self.w.scenario()
        with self.w.lock:
            pan, tilt = self.w.pan, self.w.tilt
        if self.webcam is not None:      # real images: the backend analyses them like the real robot's
            return {"zone": zone, "webcam": True}
        dist, what = self.w.ahead()
        talking = [s["name"] for s in self.w.active_sources() if self.w.heard_db(s) > 40]
        return {"zone": zone, "pan": pan, "tilt": tilt, **sc, "ahead_m": round(dist, 2), "ahead_object": what,
                "talking": talking, "students": self.w.visible_students(pan, self.hfov), "hfov_deg": self.hfov}

    def capture(self) -> np.ndarray:
        if self.webcam is not None:
            ok, frame = self.webcam.read()
            if ok:
                return frame
        zone, sc = self.w.scenario()
        with self.w.lock:
            pan = self.w.pan
        studs = self.w.visible_students(pan, self.hfov) if self.w.students else []
        key = (zone, round(pan), repr(sorted(sc.items())), repr(studs), round(self.w.theta, 2))
        if getattr(self, "_cache_key", None) != key:
            self._cache_key, self._cache = key, self._render(zone, sc, pan, studs)
        img = im.add_noise(self._cache)
        im.text(img, f"SIM CAM | {zone} | {time.strftime('%H:%M:%S')}", (8, self.H - 10), 0.5, (255, 255, 255), 1)
        return img

    def _render(self, zone: str, sc: dict, pan: float, students: list | None = None) -> np.ndarray:
        W, H = self.W, self.H
        shift = int(pan * 2)  # crude pan effect
        img = np.zeros((H, W, 3), np.uint8)
        img[:] = (190, 196, 200)                                    # wall
        im.rect(img, (0, int(H * 0.68)), (W, H), (120, 125, 135), -1)  # floor
        im.rect(img, (0, 0), (W, int(H * 0.12)), (215, 215, 215), -1)  # ceiling

        lights_on = bool(sc.get("lights_on"))
        for i in range(4):
            x = 40 + i * 150 - shift
            col = (210, 250, 255) if lights_on else (110, 110, 110)
            im.rect(img, (x, 12), (x + 100, 30), col, -1)
            if lights_on:
                im.rect(img, (x - 6, 8), (x + 106, 34), (180, 235, 245), 2)

        # projector screen
        sx = 200 - shift
        if sc.get("projector_on"):
            im.rect(img, (sx, 60), (sx + 240, 200), (255, 245, 235), -1)
            im.rect(img, (sx + 15, 75), (sx + 225, 95), (180, 90, 30), -1)
            for k in range(4):
                im.line(img, (sx + 20, 115 + k * 20), (sx + 200, 115 + k * 20), (90, 90, 90), 3)
            im.text(img, "SLIDE", (sx + 90, 92), 0.5, (255, 255, 255), 1)
        else:
            im.rect(img, (sx, 60), (sx + 240, 200), (70, 70, 70), -1)

        # benches + monitors
        for i in range(3):
            bx = 20 + i * 210 - shift
            im.rect(img, (bx, 300), (bx + 170, 320), (60, 90, 130), -1)
            mcol = (240, 200, 120) if sc.get("monitors_on") else (30, 30, 30)
            im.rect(img, (bx + 50, 250), (bx + 120, 298), (20, 20, 20), -1)
            im.rect(img, (bx + 54, 254), (bx + 116, 294), mcol, -1)
        if sc.get("hazardous_tools"):
            im.circle(img, (95 - shift, 292), 7, (0, 80, 255))
            im.line(img, (95 - shift, 292), (135 - shift, 280), (40, 40, 40), 3)
            im.text(img, "hot iron", (70 - shift, 345), 0.4, (0, 0, 200), 1)

        # emergency exit door at right
        ex = W - 120 - shift
        im.rect(img, (ex, 150), (ex + 90, 330), (40, 110, 60), -1)
        im.rect(img, (ex + 5, 120), (ex + 85, 145), (40, 170, 40), -1)
        im.text(img, "EXIT", (ex + 20, 140), 0.6, (255, 255, 255), 2)
        if sc.get("exit_blocked"):  # chair in front of the door
            im.rect(img, (ex + 10, 250), (ex + 80, 270), (20, 20, 120), -1)
            im.rect(img, (ex + 10, 200), (ex + 22, 250), (20, 20, 120), -1)
            im.line(img, (ex + 15, 270), (ex + 10, 340), (20, 20, 120), 4)
            im.line(img, (ex + 75, 270), (ex + 80, 340), (20, 20, 120), 4)
        if sc.get("extinguisher_present"):
            im.rect(img, (ex - 40, 270), (ex - 22, 325), (20, 20, 210), -1)
            im.rect(img, (ex - 36, 262), (ex - 26, 270), (30, 30, 30), -1)

        # students placed where they really are (exam hall)
        for st in students or []:
            px = int(st["x_img"] * W)
            scale = max(0.45, min(1.6, 2.2 / max(st["distance_m"], 0.5)))
            hy = int(225 - 10 * scale)
            r = int(15 * scale)
            im.rect(img, (px - int(40 * scale), 300), (px + int(40 * scale), 318), (60, 90, 130), -1)   # desk
            im.rect(img, (px - int(15 * scale), hy + r), (px + int(15 * scale), 300), (140, 60, 40), -1)  # body
            dy = int(-st["pitch"] / 90 * r * 0.9)
            im.circle(img, (px, hy + dy), r, (60, 90, 160))                                              # head
            nx = int(st["yaw"] / 90 * r)
            im.circle(img, (px + nx, hy + dy + 2), max(2, r // 4), (40, 60, 120))                        # face direction
            if "cell phone" in st["objects"]:
                im.rect(img, (px + int(8 * scale), 270), (px + int(20 * scale), 292), (20, 20, 20), -1)
                im.rect(img, (px + int(10 * scale), 272), (px + int(18 * scale), 288), (230, 200, 120), -1)
            if "notes" in st["objects"]:
                im.rect(img, (px - int(30 * scale), 292), (px - int(8 * scale), 300), (245, 245, 245), -1)
            if "earpiece" in st["objects"]:
                im.circle(img, (px - r, hy + dy), max(2, r // 5), (250, 250, 250))
        # occupants (stick figures) in rooms without placed students
        for i in range(0 if students else int(sc.get("occupants", 0))):
            px = 120 + i * 90 - shift
            im.circle(img, (px, 230), 14, (60, 90, 160))
            im.rect(img, (px - 14, 245), (px + 14, 300), (140, 60, 40), -1)

        if not lights_on:
            img = (img.astype(np.float32) * 0.35).astype(np.uint8)
            if sc.get("projector_on"):
                im.rect(img, (sx, 60), (sx + 240, 200), (255, 245, 235), -1)

        return img


def _whisper(t: np.ndarray, rng) -> np.ndarray:
    """Breathy band-limited noise (1-4 kHz) with a syllable rhythm, unit RMS."""
    noise = rng.normal(0, 1, len(t))
    hp = noise - np.convolve(noise, np.ones(8) / 8, mode="same")          # remove lows
    sig = np.convolve(hp, np.ones(3) / 3, mode="same")                      # soften the very highs
    syl = np.clip(np.sin(2 * np.pi * rng.uniform(3.0, 4.5) * t + rng.uniform(0, 6)), 0, None) ** 2
    sig = sig * syl
    return sig / (np.sqrt(np.mean(sig ** 2)) + 1e-9)


def _bang(t: np.ndarray, rng) -> np.ndarray:
    """A single knock / drop: sharp attack, fast decay, somewhere in the window. Unit peak-region RMS."""
    sig = np.zeros_like(t)
    start = int(len(t) * rng.uniform(0.2, 0.7))
    n = min(len(t) - start, int(0.12 * len(t) / max(t[-1], 1e-6)) if len(t) > 1 else 0)
    if n > 0:
        decay = np.exp(-np.arange(n) / (n / 6))
        sig[start:start + n] = rng.normal(0, 1, n) * decay
    return sig / (np.sqrt(np.mean(sig[start:start + n] ** 2)) + 1e-9) if n > 0 else sig


def _voice(t: np.ndarray, rng, f0: float) -> np.ndarray:
    """Speech-like signal with unit RMS: voiced harmonics with formants, gated by a ~4 Hz syllable rhythm."""
    pitch = f0 * (1 + 0.06 * np.sin(2 * np.pi * 0.7 * t + rng.uniform(0, 6)))
    phase = 2 * np.pi * np.cumsum(pitch) / (len(t) / max(t[-1], 1e-6) if len(t) > 1 else 16000)
    sig = np.zeros_like(t)
    for k in range(1, 18):
        fk = k * f0
        w = np.exp(-((fk - 550) / 300) ** 2) + 0.6 * np.exp(-((fk - 1600) / 450) ** 2) + 0.15
        sig += (w / k ** 0.5) * np.sin(k * phase)
    syl = np.clip(np.sin(2 * np.pi * rng.uniform(3.5, 5.0) * t + rng.uniform(0, 6)), 0, None) ** 1.5
    pauses = (np.sin(2 * np.pi * 0.45 * t + rng.uniform(0, 6)) > -0.6).astype(float)
    sig = sig * syl * pauses
    return sig / (np.sqrt(np.mean(sig ** 2)) + 1e-9)


class SimMicrophone(Microphone):
    def __init__(self, w: SimWorld):
        self.w = w

    def record(self, seconds: float, sample_rate: int) -> np.ndarray:
        _, sc = self.w.scenario()
        kind = sc.get("audio", "quiet_room")
        n = int(seconds * sample_rate)
        t = np.arange(n) / sample_rate
        rng = np.random.default_rng()
        if kind == "ac_fan":
            # broadband airflow (low-passed noise) + motor hum harmonics
            noise = rng.normal(0, 1, n)
            noise = np.convolve(noise, np.ones(12) / 12, mode="same")
            sig = 0.18 * noise / (np.std(noise) + 1e-9) + 0.05 * np.sin(2 * np.pi * 100 * t) + 0.03 * np.sin(2 * np.pi * 150 * t)
        elif kind == "crowd":
            # many voices: loudness swells and dips several times a second (alternate loud/quiet segments,
            # so even a 1 s clip always has the strong modulation real crowd noise has)
            k = int(seconds * 8) + 1
            levels = np.where(np.arange(k) % 2 == 0, rng.uniform(0.6, 1.0, k), rng.uniform(0.1, 0.35, k))
            env = np.repeat(levels, sample_rate // 8)[:n]
            noise = rng.normal(0, 1, n)
            noise = np.convolve(noise, np.ones(4) / 4, mode="same")
            sig = 0.35 * env * noise / (np.std(noise) + 1e-9) + 0.08 * np.sin(2 * np.pi * 220 * t) * env
        elif kind == "alarm":
            gate = (np.floor(t * 4) % 2 == 0).astype(float)
            sig = 0.5 * gate * np.sin(2 * np.pi * 3100 * t) + rng.normal(0, 0.01, n)
        else:  # quiet room
            sig = rng.normal(0, 0.004, n)
        for src in getattr(self.w, "active_sources", lambda: [])():
            spl = self.w.heard_db(src)
            amp = 10 ** ((spl - 83.0) / 20.0)          # same calibration as the analyser (dBFS + 83)
            kind = src.get("kind", "speech")
            if kind == "whisper":
                sig = sig + amp * _whisper(t, rng)
            elif kind == "bang":
                sig = sig + amp * _bang(t, rng)
            else:
                sig = sig + amp * _voice(t, rng, float(src.get("f0", 135 + 40 * (hash(src.get("name")) % 3))))
        time.sleep(min(seconds, 0.2))  # pretend we are recording (shortened)
        return np.clip(sig * 32767, -32768, 32767).astype(np.int16)


class SimSpeaker(Speaker):
    def say(self, text: str) -> None:
        log.info("[SPEAKER] %s", text)

    def beep(self, kind: str = "info") -> None:
        log.info("[SPEAKER] beep (%s)", kind)


class SimPhoneSpeaker(Speaker):
    """The ESP32 robot has no speaker: the phone app speaks instead."""

    present = False

    def say(self, text: str) -> None:
        log.info("[no speaker on the robot] %s", text)


class SimBattery(Battery):
    def __init__(self, w: SimWorld, cells: int = 3):
        self.w = w
        self.cells = cells

    def read(self) -> BatteryReading:
        with self.w.lock:
            pct = self.w.battery_pct
        volts = self.cells * (3.3 + 0.9 * pct / 100.0)
        return BatteryReading(voltage=round(volts, 2), percent=round(pct, 1), charging=False)


SIM_PARTS = {
    "esp32": {"motors": "simulated DRV8833 + 2 TT motors (2WD)",
              "pan_tilt": "fixed camera: the robot turns to look around",
              "ultrasonic": "simulated HC-SR04P at the front", "encoders": "not fitted: distance from motor time + MPU6050 heading",
              "imu": "simulated MPU6050", "environment": "simulated AHT20 + BMP280 · no gas sensor fitted",
              "camera": "simulated XIAO ESP32S3 Sense camera", "microphone": "simulated XIAO ESP32S3 Sense microphone",
              "speaker": "no speaker: the phone app speaks and shows alerts",
              "battery": "not measured: ESP32 on a power bank (see its LEDs), motors on 2 x 18650"},
    "budget": {"motors": "simulated L298N + 4 TT motors, speed on GPIO 13/19",
               "pan_tilt": "fixed camera: the robot turns to look around",
               "ultrasonic": "simulated 3x HC-SR04", "encoders": "not fitted: distance from motor time + MPU6050 heading",
               "imu": "simulated MPU6050", "environment": "simulated AHT20 + BMP280 · no gas sensor fitted",
               "camera": "simulated USB webcam", "microphone": "simulated webcam microphone",
               "speaker": "simulated PAM8403 on the audio jack",
               "battery": "not measured: Pi on a power bank (see its LEDs), motors on 2 x 18650"},
    "full": {"motors": "simulated PCA9685 + L298N", "pan_tilt": "simulated pan/tilt servos",
             "ultrasonic": "simulated 3x HC-SR04", "encoders": "simulated", "imu": "simulated MPU6050",
             "environment": "simulated BME680 + MQ-135", "camera": "simulated Pi Camera",
             "microphone": "simulated USB microphone", "speaker": "simulated speaker", "battery": "simulated UPS gauge"},
}


class _NoEncoders(Encoders):
    def ticks(self) -> tuple[int, int]:
        return 0, 0


class _NoBattery(Battery):
    def read(self) -> BatteryReading:
        return BatteryReading(None, None)


def create_sim_hardware(cfg: dict) -> Hardware:
    build = str(cfg.get("sim_build") or "esp32").lower()
    build = build if build in SIM_PARTS else "esp32"
    esp32 = build == "esp32"
    budget = build in ("budget", "esp32")      # both: no encoders, no gas sensor, no battery gauge, fixed camera
    world = load_sim_world(cfg.get("sim_world_path"))
    w = SimWorld(cfg, world)
    hc = cfg.get("hardware", {})
    cells = int(hc.get("battery_cells", 3))
    hw = Hardware(
        motors=SimMotors(w),
        pan_tilt=SimPanTilt(w),
        ultrasonics=SimUltrasonics(w, front_only=esp32),
        encoders=_NoEncoders() if budget else SimEncoders(w),
        imu=SimImu(w),
        env=SimEnv(w, cfg, voc=not budget, gas=not budget),
        camera=SimCamera(w, cfg),
        microphone=SimMicrophone(w),
        speaker=SimPhoneSpeaker() if esp32 else SimSpeaker(),
        battery=_NoBattery() if budget else SimBattery(w, cells),
        simulated=True,
        health={k: {"ok": True, "detail": d, "hint": ""} for k, d in SIM_PARTS[build].items()},
        extra={"world": w, "gas_baseline_ohm": None if budget else SIM_GAS_BASELINE_OHM,
               "fixed_camera": budget, "build": build, "encoders": not budget, "motor_deadband": 0.0},
    )
    _orig_close = hw.close

    def _close():
        _orig_close()
        w.stop()

    hw.close = _close  # type: ignore[method-assign]
    return hw
