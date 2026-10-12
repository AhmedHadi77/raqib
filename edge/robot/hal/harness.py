"""Virtual wiring harness: the simulated robot works only as well as you wired it on the Wiring Bench.

When enabled (from the app's Wiring Bench), every simulated part (2D simulator or Webots) is checked
against the wires you made to the virtual Raspberry Pi, and behaves the way the real part would:

  * not connected          -> the part is dead, exactly like a missing part on the real robot
                              (no distance reading = forward driving refused, no encoder ticks, no camera...)
  * IN1 / IN2 swapped      -> that side of the robot drives backwards
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

from ..wiring_spec import HEADER, PARTS
from .base import (Battery, BatteryReading, Camera, Encoders, EnvRaw, EnvSensor, Hardware, Imu, ImuReading,
                   Microphone, Motors, PanTilt, Speaker, Ultrasonics)

log = logging.getLogger(__name__)

PART = {p["id"]: p for p in PARTS}
POWER = ("p5", "p33")
SW_PINS = {11: ("L", 1), 13: ("L", -1), 15: ("R", 1), 16: ("R", -1)}     # L298N inputs as the software drives them
SW_PWM = {"pca0": "L", "pca1": "R"}
US_KEYS = ("left", "center", "right")


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
    return f"pin {n} ({HEADER[n][0]})" if n else target


def evaluate(wires: dict[str, str]) -> dict:
    """Judge a set of wires {"part.pin": target} the way the real robot would behave."""
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
                shorts.append(f"{label} (11.1 V battery) on the Pi's {_where(t)}: this would destroy the Pi")
            elif want in POWER and t == "bat+":
                warnings.append(f"{label} on the 11.1 V battery: the part would burn out")
            elif want in POWER and t == "bat-" or want == "ext:bat+" and t == "bat-" or want == "gnd" and t == "bat+":
                shorts.append(f"{label} on {t}: the battery is shorted")
            elif want in ("gpio", "sda", "scl") and got in POWER + ("gnd",):
                warnings.append(f"{label} on {_where(t)}: a signal pin on a power or ground pin")
            elif want == "p33" and got == "p5":
                warnings.append(f"{label} on 5 V: this 3.3 V part would burn out")

    def vcc_ok(part, pin="vcc"):
        return pins[f"{part}.{pin}"]["status"] == "ok" and pins[f"{part}.gnd"]["status"] == "ok"

    def i2c(part, pin="vcc"):
        if not vcc_ok(part, pin):
            return False, "no power (check VCC and GND)"
        sda, scl = _pin(w(part, "sda")), _pin(w(part, "scl"))
        if sda == 5 and scl == 3:
            return False, "SDA and SCL are swapped, so it does not answer on I2C"
        if sda != 3 or scl != 5:
            return False, "not on the I2C bus (SDA must be pin 3, SCL pin 5)"
        return True, ""

    power = w("ups", "in+") == "bat+" and w("ups", "in-") == "bat-"
    eff: dict = {"power": power and not shorts, "shorts": shorts, "warnings": warnings}
    on = eff["power"]

    # ---------------- PCA9685 + L298N + motors
    pca_ok, pca_why = i2c("pca")
    servo_power = w("pca", "v+") == "ups5"
    l298_power = w("l298", "12v") == "bat+" and w("l298", "gndbat") == "bat-"
    common_gnd = _cls(w("l298", "gndpi")) == "gnd"

    def channel(en, a, b):
        side = SW_PWM.get(w("l298", en) or "")
        pa, pb = SW_PINS.get(_pin(w("l298", a)) or 0), SW_PINS.get(_pin(w("l298", b)) or 0)
        if not side or not pa or not pb or pa[0] != side or pb[0] != side or pa[1] == pb[1]:
            return None
        return side, pa[1]

    chans = {"out12": channel("ena", "in1", "in2"), "out34": channel("enb", "in3", "in4")}
    wheels = {}
    for phys in ("left", "right"):
        out = w("motors", phys)
        wheels[phys] = chans.get(out) if (on and pca_ok and l298_power and common_gnd and out in chans) else None
    eff["wheels"] = wheels

    # ---------------- servos
    servo = {}
    for phys in ("pan", "tilt"):
        ch = {"pca14": "pan", "pca15": "tilt"}.get(w("servos", phys) or "")
        servo[phys] = ch if (on and pca_ok and servo_power and ch) else None
    eff["servos"] = servo

    # ---------------- ultrasonics: software key -> physical sensor answering on its pins
    us = {}
    for k in US_KEYS:
        trig, echo = PART[f"us_{k}"]["pins"][2]["spec"]["pin"], PART[f"us_{k}"]["pins"][3]["spec"]["pin"]
        src = None
        for phys in US_KEYS:
            pid = f"us_{phys}"
            if vcc_ok(pid) and _pin(w(pid, "trig")) == trig and _pin(w(pid, "echo")) == echo:
                src = phys
        us[k] = src if on else None
    eff["ultrasonic"] = us

    # ---------------- encoders
    enc = {}
    for k, pin in (("left", 29), ("right", 31)):
        src = None
        for phys in ("left", "right"):
            if vcc_ok("enc") and _pin(w("enc", phys)) == pin:
                src = phys
        enc[k] = src if on else None
    eff["encoders"] = enc

    imu_ok, imu_why = i2c("imu")
    bme_ok, bme_why = i2c("bme")
    ads_ok, ads_why = i2c("ads", "vdd")
    addr = _cls(w("ads", "addr"))
    if ads_ok and addr != "gnd":
        ads_ok, ads_why = False, ("ADDR is on 3.3 V, so it answers at 0x49 but config.yaml expects 0x48" if addr == "p33"
                                  else "ADDR is not connected, so its I2C address is random")
    mq_ok = vcc_ok("mq") and w("mq", "aout") == "adsa0" and ads_ok
    eff.update({
        "imu": on and imu_ok, "bme": on and bme_ok, "gas": on and mq_ok,
        "camera": on and w("cam", "ribbon") == "csi",
        "microphone": on and w("mic", "usb") == "usb",
        "speaker": on and vcc_ok("spk") and w("spk", "in") == "usbaudio",
        "battery": on,
    })
    burnt = {msg.split(" ")[0] for msg in warnings if "burn" in msg}
    if burnt:
        log.warning("wiring: %s", "; ".join(warnings))

    # ---------------- health entries for the app (same keys as the real robot)
    H: dict = {}

    def put(key, ok, detail, hint=""):
        H[key] = {"ok": bool(ok), "detail": detail, "hint": hint}

    if shorts:
        put("power", False, "SHORT CIRCUIT - " + shorts[0], "Remove that wire on the Wiring Bench. The robot is off until you do.")
    elif not power:
        put("power", False, "No power: the UPS hat is not connected to the battery", "Wire UPS hat Battery in + / - to the battery.")
    else:
        put("power", True, "Battery -> UPS hat -> Raspberry Pi")
    put("i2c", on, "pins 3 (SDA) and 5 (SCL)" if on else "Pi is off")

    def side_txt(phys):
        c = wheels[phys]
        if c is None:
            return None
        txt = []
        if c[0] != phys[0].upper():
            txt.append(f"driven by the {'left' if c[0] == 'L' else 'right'}-side signals")
        if c[1] < 0:
            txt.append("run backwards")
        return ", ".join(txt)

    if not on:
        put("motors", False, "no power")
    elif not pca_ok:
        put("motors", False, f"PCA9685 {pca_why}", "PCA9685: VCC 3.3 V, GND, SDA pin 3, SCL pin 5.")
    elif not l298_power:
        put("motors", False, "L298N has no motor power", "L298N +12V to Battery +, GND to Battery -.")
    elif not common_gnd:
        put("motors", False, "L298N ground is not joined to the Pi ground", "Wire L298N GND (to Pi) to any GND pin.")
    elif None in wheels.values():
        dead = [k for k, v in wheels.items() if v is None]
        put("motors", False, f"{' and '.join(dead)} wheels do not turn",
            "Check ENA/ENB on PCA9685 ch0/ch1, IN1-IN4 on GPIO 17/27/22/23 and the motor pairs on OUT1-OUT4.")
    else:
        odd = [f"{k} wheels {side_txt(k)}" for k in ("left", "right") if side_txt(k)]
        put("motors", not odd, "; ".join(odd) if odd else "L298N + PCA9685, both sides OK",
            "Swap IN1/IN2 (or IN3/IN4) to reverse a side; check which pair is on OUT1/OUT2." if odd else "")
    if not on:
        put("pan_tilt", False, "no power")
    elif not servo_power:
        put("pan_tilt", False, "servos have no power", "PCA9685 V+ to the UPS 5 V servo output.")
    elif None in servo.values():
        put("pan_tilt", False, "a servo is not plugged in", "Pan on channel 14, tilt on channel 15.")
    elif servo["pan"] != "pan":
        put("pan_tilt", False, "pan and tilt are swapped", "Pan servo on channel 14, tilt on channel 15.")
    else:
        put("pan_tilt", True, "servos on ch14 / ch15")
    bad_us = [k for k, v in us.items() if v != k]
    put("ultrasonic", not bad_us,
        "3x HC-SR04 OK" if not bad_us else "; ".join(f"{k}: " + ("no reading" if us[k] is None else f"reads the {us[k]} sensor")
                                                      for k in bad_us),
        "" if not bad_us else "Each sensor: VCC 5 V, GND, TRIG and ECHO on its own GPIO pair (see config.yaml). "
                              "No reading in front = forward driving is refused.")
    bad_enc = [k for k, v in enc.items() if v != k]
    put("encoders", not bad_enc, "GPIO 5 / 6" if not bad_enc else
        "; ".join(f"{k}: " + ("no ticks" if enc[k] is None else f"counts the {enc[k]} wheel") for k in bad_enc),
        "" if not bad_enc else "VCC 3.3 V, GND, left OUT on pin 29 (GPIO 5), right OUT on pin 31 (GPIO 6).")
    put("imu", eff["imu"], "MPU6050 at 0x68" if eff["imu"] else ("no power" if not on else f"MPU6050 {imu_why}"))
    env_detail = ("BME680 + MQ-135" if eff["bme"] and eff["gas"] else
                  "BME680 only: " + ("MQ-135 / ADS1115 " + (ads_why or "not wired")) if eff["bme"] else
                  "no power" if not on else f"BME680 {bme_why}")
    put("environment", eff["bme"] and eff["gas"], env_detail,
        "" if eff["bme"] and eff["gas"] else "BME680 + ADS1115 on I2C (3.3 V), MQ-135 on 5 V with AOUT -> divider -> A0.")
    put("camera", eff["camera"], "ribbon in the CSI port" if eff["camera"] else "no power" if not on else "ribbon cable not in the CSI port")
    put("microphone", eff["microphone"], "USB" if eff["microphone"] else "no power" if not on else "not plugged into USB")
    put("speaker", eff["speaker"], "PAM8403 + speaker" if eff["speaker"] else "no power" if not on else
        "amplifier needs 5 V, GND and audio from the USB sound card")
    put("battery", on, "UPS hat gauge (0x42)" if on else "no power")
    for msg in warnings:
        H.setdefault("wiring", {"ok": False, "detail": msg, "hint": "Fix that wire on the Wiring Bench."})

    done = sum(1 for v in pins.values() if v["status"] == "ok")
    return {"pins": pins, "effects": eff, "health": H, "done": done, "total": len(pins),
            "drivable": bool(on and wheels["left"] == ("L", 1) and wheels["right"] == ("R", 1) and us.get("center") == "center"
                             and eff["imu"] and enc == {"left": "left", "right": "right"})}


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
    def set_angles(self, pan_deg, tilt_deg):
        h = self._h
        if not h.enabled:
            return self._inner.set_angles(pan_deg, tilt_deg)
        ch = {"pan": pan_deg, "tilt": tilt_deg}
        s = h.eff["servos"]
        self._last = getattr(self, "_last", [0.0, 0.0])
        if s.get("pan"):
            self._last[0] = ch[s["pan"]]
        if s.get("tilt"):
            self._last[1] = ch[s["tilt"]]
        self._inner.set_angles(*self._last)


class HUltrasonics(_Proxy, Ultrasonics):
    def read_cm(self):
        r = self._inner.read_cm()
        h = self._h
        if not h.enabled:
            return r
        return {k: (r.get(src, 0.0) if src else 0.0) for k, src in h.eff["ultrasonic"].items()}


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
        if not h.eff["bme"]:
            raise RuntimeError("BME680 not found on I2C - check its wiring on the Wiring Bench")
        r = self._inner.read()
        if not h.eff["gas"]:
            r = EnvRaw(r.temperature_c, r.humidity_pct, r.pressure_hpa, r.gas_resistance_ohm, None)
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
