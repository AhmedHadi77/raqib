"""Virtual wiring harness: the simulated robot works only as well as you wired it on the Wiring Bench.

When enabled (from the app's Wiring Bench), every simulated part (2D simulator or Webots) is checked
against the wires you made to the virtual XIAO ESP32S3, and behaves the way the real part would:

  * not connected          -> the part is dead, exactly like a missing part on the real robot
                              (no distance reading = forward driving refused, no encoder ticks, no camera...)
  * AIN1 / AIN2 swapped    -> that side of the robot drives backwards
  * sensors on each other's pins -> left and right readings swapped
  * 5 V on a 3.3 V part    -> the part is "burnt" until you fix the wire
  * power to ground        -> short circuit: the whole robot is off

Robot health in the app shows every problem with what to fix. Turned off, the robot works as before.
"""
from __future__ import annotations

import copy
import logging
import threading

import numpy as np

from ..wiring_spec import D, HEADER, PARTS
from .base import (Battery, BatteryReading, Camera, Encoders, EnvRaw, EnvSensor, Hardware, Imu, ImuReading,
                   Microphone, Motors, PanTilt, Speaker, Ultrasonics)

log = logging.getLogger(__name__)

PART = {p["id"]: p for p in PARTS}
POWER = ("p5", "p33")
SW_PINS = {D["D0"]: ("L", 1), D["D1"]: ("L", -1), D["D2"]: ("R", 1), D["D3"]: ("R", -1)}   # how the firmware drives the DRV8833
US_KEYS = ("left", "center", "right")
NOT_FITTED = "nofit"                    # the ESP32 robot has one distance sensor, at the front


def _cls(target: str | None) -> str | None:
    if target and target.startswith("pin:"):
        return HEADER[int(target[4:])][1]
    return None


def _pin(target: str | None) -> int | None:
    return int(target[4:]) if target and target.startswith("pin:") else None


def _spec_cls(spec: dict) -> str:
    if "cls" in spec:
        return spec["cls"]
    if "pin" in spec:
        return HEADER[spec["pin"]][1]
    return "ext:" + spec["ext"]


def _matches(spec: dict, target: str | None) -> bool:
    if not target:
        return False
    if "ext" in spec:
        return target == spec["ext"]
    if "cls" in spec:
        return _cls(target) == spec["cls"]
    return _pin(target) == spec["pin"]


def _where(target: str) -> str:
    n = _pin(target)
    return f"{HEADER[n][0].split(' ·')[0]}" if n else target


def evaluate(wires: dict[str, str]) -> dict:
    """Judge a set of wires {"part.pin": target} the way the real ESP32 robot would behave."""
    w = lambda part, pin: wires.get(f"{part}.{pin}")  # noqa: E731
    pins, warnings, shorts = {}, [], []
    for p in PARTS:
        for pin in p["pins"]:
            key = f"{p['id']}.{pin['id']}"
            t = wires.get(key)
            spec = pin["spec"]
            st = "missing" if not t else "ok" if _matches(spec, t) else "wrong"
            pins[key] = {"status": st, "target": t}
            if st != "wrong":
                continue
            want, got = _spec_cls(spec), _cls(t)
            label = f"{p['name']} {pin['label']}"
            if want == "gnd" and got in POWER or want in POWER and got == "gnd":
                shorts.append(f"{label} on {_where(t)}: power is wired straight to ground")
            elif want == "ext:bat+" and got:
                shorts.append(f"{label} (7.4 V battery) on the XIAO's {_where(t)}: this would destroy the ESP32")
            elif want in POWER and t == "bat+":
                warnings.append(f"{label} on the 7.4 V battery: the part would burn out")
            elif want in POWER and t == "bat-" or want == "ext:bat+" and t == "bat-" or want == "gnd" and t == "bat+":
                shorts.append(f"{label} on {t}: the battery is shorted")
            elif want in ("gpio", "sda", "scl") and got in POWER + ("gnd",):
                warnings.append(f"{label} on {_where(t)}: a signal pin on a power or ground pin")
            elif want == "p33" and got == "p5":
                warnings.append(f"{label} on 5 V: this 3.3 V part would burn out" if p["id"] != "us" else
                                f"{label} on 5 V: its ECHO would put 5 V on D7 and burn that pin")

    def vcc_ok(part, pin="vcc"):
        return pins[f"{part}.{pin}"]["status"] == "ok" and pins[f"{part}.gnd"]["status"] == "ok"

    def i2c(part, pin="vcc"):
        if not vcc_ok(part, pin):
            return False, "no power (check VCC and GND)"
        sda, scl = _pin(w(part, "sda")), _pin(w(part, "scl"))
        if sda == D["D5"] and scl == D["D4"]:
            return False, "SDA and SCL are swapped, so it does not answer on I2C"
        if sda != D["D4"] or scl != D["D5"]:
            return False, "not on the I2C bus (SDA must be D4, SCL D5)"
        return True, ""

    power = w("pbank", "usb") == "usbc"
    eff: dict = {"power": power and not shorts, "shorts": shorts, "warnings": warnings}
    on = eff["power"]

    # ---------------- DRV8833 + motors
    drv_power = w("drv", "vm") == "bat+" and w("drv", "gndbat") == "bat-"
    drv_awake = _cls(w("drv", "eep")) == "p33"
    common_gnd = _cls(w("drv", "gndx")) == "gnd"

    def channel(a, b):
        pa, pb = SW_PINS.get(_pin(w("drv", a)) or 0), SW_PINS.get(_pin(w("drv", b)) or 0)
        if not pa or not pb or pa[0] != pb[0] or pa[1] == pb[1]:
            return None
        return pa[0], pa[1]

    chans = {"aout": channel("ain1", "ain2"), "bout": channel("bin1", "bin2")}
    wheels = {}
    for phys in ("left", "right"):
        out = w("motors", phys)
        wheels[phys] = chans.get(out) if (on and drv_power and common_gnd and drv_awake and out in chans) else None
    eff["wheels"] = wheels

    # ---------------- the one distance sensor (front)
    us_ok = on and vcc_ok("us") and _pin(w("us", "trig")) == D["D6"] and _pin(w("us", "echo")) == D["D7"]
    eff["ultrasonic"] = {"left": NOT_FITTED, "center": "center" if us_ok else None, "right": NOT_FITTED}
    eff["encoders"] = {"left": None, "right": None}

    imu_ok, imu_why = i2c("imu")
    aht_ok, aht_why = i2c("aht")
    sense = on and w("sense", "b2b") == "b2b"
    eff.update({
        "imu": on and imu_ok, "climate": on and aht_ok, "gas": False,
        "camera": sense and w("sense", "cam") == "camsock", "microphone": sense,
        "speaker": False, "battery": False,
    })
    if warnings:
        log.warning("wiring: %s", "; ".join(warnings))

    # ---------------- health entries for the app (same keys as the real robot)
    H: dict = {}

    def put(key, ok, detail, hint=""):
        H[key] = {"ok": bool(ok), "detail": detail, "hint": hint}

    if shorts:
        put("power", False, "SHORT CIRCUIT - " + shorts[0], "Remove that wire on the Wiring Bench. The robot is off until you do.")
    elif not power:
        put("power", False, "No power: the XIAO is not connected to the power bank",
            "Plug the power bank's USB-C cable into the XIAO.")
    else:
        put("power", True, "Power bank -> XIAO ESP32S3; motors on their own 2 x 18650 pack")
    put("i2c", on, "D4 (SDA) and D5 (SCL)" if on else "the XIAO is off")

    def side_txt(phys):
        c = wheels[phys]
        if c is None:
            return None
        txt = []
        if c[0] != phys[0].upper():
            txt.append(f"driven by the {'left' if c[0] == 'L' else 'right'}-motor signals")
        if c[1] < 0:
            txt.append("runs backwards")
        return ", ".join(txt)

    if not on:
        put("motors", False, "no power")
    elif not drv_power:
        put("motors", False, "DRV8833 has no motor power", "DRV8833 VM to Battery +, GND to Battery -.")
    elif not common_gnd:
        put("motors", False, "DRV8833 ground is not joined to the XIAO ground",
            "With two batteries this wire is essential: DRV8833 GND (to XIAO) to the GND rail.")
    elif not drv_awake:
        put("motors", False, "DRV8833 is asleep: EEP is not on 3.3 V",
            "DRV8833 EEP (or SLP / STBY) to the 3V3 rail. Left open, the driver stays asleep.")
    elif None in wheels.values():
        dead = [k for k, v in wheels.items() if v is None]
        put("motors", False, f"{' and '.join(dead)} wheel does not turn",
            "AIN1/AIN2 on D0/D1, BIN1/BIN2 on D2/D3, the left motor on AOUT, the right motor on BOUT.")
    else:
        odd = [f"{k} wheel {side_txt(k)}" for k in ("left", "right") if side_txt(k)]
        put("motors", not odd, "; ".join(odd) if odd else "DRV8833 on D0-D3, both wheels OK",
            "Swap AIN1/AIN2 (or BIN1/BIN2) to reverse a side; check which motor is on AOUT and BOUT." if odd else "")
    put("pan_tilt", on, "fixed camera: the robot turns to look around" if on else "no power")
    put("ultrasonic", us_ok, "HC-SR04P at the front OK" if us_ok else "no reading" if on else "no power",
        "" if us_ok else "HC-SR04P: VCC 3V3, GND, TRIG on D6, ECHO on D7. No reading = forward driving is refused.")
    put("encoders", on, "not fitted: distance from motor time + MPU6050 heading" if on else "no power")
    put("imu", eff["imu"], "MPU6050 at 0x68" if eff["imu"] else ("no power" if not on else f"MPU6050 {imu_why}"))
    put("environment", eff["climate"], "AHT20 + BMP280 · no gas sensor fitted" if eff["climate"] else
        "no power" if not on else f"AHT20 {aht_why}",
        "" if eff["climate"] else "AHT20 + BMP280 on I2C: VIN 3V3, GND, SDA on D4, SCL on D5.")
    put("camera", eff["camera"], "XIAO Sense camera" if eff["camera"] else "no power" if not on else
        "camera not connected: Sense board on the XIAO and the ribbon in its socket")
    put("microphone", eff["microphone"], "XIAO Sense microphone" if eff["microphone"] else "no power" if not on else
        "the Sense board (with the microphone) is not on the XIAO")
    put("speaker", True, "no speaker: the phone app speaks and shows alerts")
    put("battery", on, "not measured: ESP32 on a power bank (see its LEDs), motors on 2 x 18650" if on else "no power")
    for msg in warnings:
        H.setdefault("wiring", {"ok": False, "detail": msg, "hint": "Fix that wire on the Wiring Bench."})

    done = sum(1 for v in pins.values() if v["status"] == "ok")
    return {"pins": pins, "effects": eff, "health": H, "done": done, "total": len(pins),
            "drivable": bool(on and wheels["left"] == ("L", 1) and wheels["right"] == ("R", 1) and us_ok and eff["imu"])}


# ============================================================================ part proxies
class _Proxy:
    def __init__(self, inner, harness):
        self._inner, self._h = inner, harness

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def close(self):
        self._inner.close()


class HMotors(_Proxy, Motors):
    def set_wheels(self, left, right):
        h = self._h
        if not h.enabled:
            return self._inner.set_wheels(left, right)
        cmd = {"L": left, "R": right}
        out = []
        for phys in ("left", "right"):
            c = h.eff["wheels"].get(phys)
            out.append(cmd[c[0]] * c[1] if c else 0.0)
        self._inner.set_wheels(*out)


class HPanTilt(_Proxy, PanTilt):
    """The budget robot has no servos: while the bench wiring is on, the camera stays straight ahead
    (the robot turns its body to look, see RobotApp._virtual_pan)."""

    def set_angles(self, pan_deg, tilt_deg):
        if not self._h.enabled:
            return self._inner.set_angles(pan_deg, tilt_deg)
        self._inner.set_angles(0.0, 0.0)


class HUltrasonics(_Proxy, Ultrasonics):
    def read_cm(self):
        r = self._inner.read_cm()
        h = self._h
        if not h.enabled:
            return r
        return {k: 400.0 if src == NOT_FITTED else (r.get(src, 0.0) if src else 0.0) for k, src in h.eff["ultrasonic"].items()}


class HEncoders(_Proxy, Encoders):
    def __init__(self, inner, harness):
        super().__init__(inner, harness)
        self._frozen = {"left": 0, "right": 0}
        self._off = {"left": 0, "right": 0}

    def ticks(self):
        tl, tr = self._inner.ticks()
        h = self._h
        if not h.enabled:
            return tl, tr
        phys = {"left": tl, "right": tr}
        out = []
        for k in ("left", "right"):
            src = h.eff["encoders"].get(k)
            if src:
                v = phys[src] - self._off[k]
                self._frozen[k] = v
            else:
                v = self._frozen[k]
            out.append(v)
        return tuple(out)

    def rebase(self):
        """Keep counts continuous when the wiring changes."""
        tl, tr = self._inner.ticks()
        phys = {"left": tl, "right": tr}
        for k in ("left", "right"):
            src = self._h.eff["encoders"].get(k)
            if src:
                self._off[k] = phys[src] - self._frozen[k]


class HImu(_Proxy, Imu):
    def read(self):
        return self._inner.read() if not self._h.enabled or self._h.eff["imu"] else ImuReading()


class HEnv(_Proxy, EnvSensor):
    def read(self):
        h = self._h
        if not h.enabled:
            return self._inner.read()
        if not h.eff["climate"]:
            raise RuntimeError("AHT20 not found on I2C - check its wiring on the Wiring Bench")
        r = self._inner.read()
        if not h.eff["gas"]:
            r = EnvRaw(r.temperature_c, r.humidity_pct, r.pressure_hpa, None, None)
        return r


class HCamera(_Proxy, Camera):
    def capture(self):
        h = self._h
        if not h.enabled or h.eff["camera"]:
            return self._inner.capture()
        from .real import NullCamera

        return NullCamera().capture()

    def scene_truth(self):
        h = self._h
        return self._inner.scene_truth() if not h.enabled or h.eff["camera"] else None


class HMicrophone(_Proxy, Microphone):
    def record(self, seconds, sample_rate):
        h = self._h
        if not h.enabled or h.eff["microphone"]:
            return self._inner.record(seconds, sample_rate)
        return np.zeros(int(seconds * sample_rate), np.int16)


class HSpeaker(_Proxy, Speaker):
    def say(self, text):
        h = self._h
        if not h.enabled or h.eff["speaker"]:
            return self._inner.say(text)
        log.info("[SPEAKER not wired] %s", text)

    def beep(self, kind="info"):
        if not self._h.enabled or self._h.eff["speaker"]:
            return self._inner.beep(kind)


class HBattery(_Proxy, Battery):
    def read(self):
        return self._inner.read() if not self._h.enabled or self._h.eff["battery"] else BatteryReading(None, None)


class Harness:
    def __init__(self, hw: Hardware):
        self.hw = hw
        self.lock = threading.Lock()
        self.enabled = False
        self.wires: dict[str, str] = {}
        self.report = evaluate({})
        self.eff = self.report["effects"]
        self.base_health = copy.deepcopy(hw.health)
        self.base_fixed = bool(hw.extra.get("fixed_camera"))
        hw.motors = HMotors(hw.motors, self)
        hw.pan_tilt = HPanTilt(hw.pan_tilt, self)
        hw.ultrasonics = HUltrasonics(hw.ultrasonics, self)
        hw.encoders = self.encoders = HEncoders(hw.encoders, self)
        hw.imu = HImu(hw.imu, self)
        hw.env = HEnv(hw.env, self)
        hw.camera = HCamera(hw.camera, self)
        hw.microphone = HMicrophone(hw.microphone, self)
        hw.speaker = HSpeaker(hw.speaker, self)
        hw.battery = HBattery(hw.battery, self)
        hw.extra["harness"] = self

    def set(self, enabled: bool, wires: dict | None = None) -> dict:
        with self.lock:
            if wires is not None:
                self.wires = {str(k): str(v) for k, v in wires.items() if v}
            self.enabled = bool(enabled)
            self.report = evaluate(self.wires)
            self.eff = self.report["effects"]
            self.encoders.rebase()
            self.hw.health.clear()
            self.hw.health.update(copy.deepcopy(self.base_health) if not self.enabled else self.report["health"])
            self.hw.extra["fixed_camera"] = True if self.enabled else self.base_fixed
            if self.enabled:
                self.hw.pan_tilt.set_angles(0.0, 0.0)
            if self.enabled:
                self.hw.motors.set_wheels(0.0, 0.0)
        return self.status()

    def status(self) -> dict:
        r = self.report
        return {"enabled": self.enabled, "wires": self.wires, "pins": r["pins"], "health": r["health"],
                "done": r["done"], "total": r["total"], "drivable": r["drivable"],
                "shorts": r["effects"]["shorts"], "warnings": r["effects"]["warnings"]}


def install_harness(hw: Hardware) -> Harness:
    return Harness(hw)
