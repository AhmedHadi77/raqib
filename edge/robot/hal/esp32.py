"""ESP32 robot over Wi-Fi: the XIAO ESP32S3 Sense is the body, this PC program is the brain.

The firmware (esp32/raqib_esp32) drives the two motors, reads the sensors and serves the
camera and microphone over HTTP. This module turns that into the same HAL the simulator and
the Raspberry Pi use, so navigation, safety, inspections and exam monitoring do not change.

    control  http://<robot>/status  /drive?l=&r=  /stop  /config  /capture  /reset_yaw
    audio    http://<robot>:82/audio?ms=1000      (WAV, 16 kHz mono)

Safety is in two places: the firmware stops by itself (0.6 s dead-man, <15 cm ahead), and the
usual safety monitor on this PC watches the same distance.
"""
from __future__ import annotations

import http.client
import io
import json
import logging
import socket
import threading
import time
import wave

import numpy as np

from .base import (
    Battery, BatteryReading, Camera, Encoders, EnvRaw, EnvSensor, Hardware, Imu, ImuReading, Microphone, Motors,
    PanTilt, Speaker, Ultrasonics,
)

log = logging.getLogger(__name__)

BEACON_PORT = 37021
CONTROL_HZ = 20

HINTS = {
    "link": "The robot is not answering on Wi-Fi. Is it switched on (power bank) and on the same Wi-Fi as this PC? "
            "Its LED is steady when it is on Wi-Fi. Open http://raqib.local in a browser, or set hardware.esp32_host "
            "to the address it shows on its test page.",
    "motors": "DRV8833: AIN1/AIN2 on D0/D1 (left motor), BIN1/BIN2 on D2/D3 (right motor), VM to the motor battery +, "
              "and the DRV8833 GND joined to the XIAO GND. Run: python -m hwtest.test_motors",
    "ultrasonic": "HC-SR04P (3.3 V version): VCC to 3V3, TRIG to D6, ECHO to D7, GND to GND. Run: python -m hwtest.test_sensors",
    "imu": "MPU6050: VCC 3V3, GND, SDA to D4, SCL to D5. Keep the robot still for 2 s after switching on.",
    "environment": "AHT20 + BMP280: VIN 3V3, GND, SDA to D4, SCL to D5 (the same wires as the MPU6050).",
    "camera": "The camera ribbon of the Sense board must click into its socket; flash the firmware with PSRAM: OPI PSRAM.",
    "microphone": "The microphone is on the Sense expansion board: press the board firmly onto the XIAO.",
}


# ============================================================================ finding the robot
def discover(timeout_s: float = 6.0) -> str | None:
    """Listen for the robot's 'RAQIB-ESP32 <version> <ip>' broadcast (sent every 2 s)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", BEACON_PORT))
        s.settimeout(0.5)
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            try:
                data, addr = s.recvfrom(256)
            except socket.timeout:
                continue
            parts = data.decode(errors="ignore").split()
            if len(parts) >= 3 and parts[0] == "RAQIB-ESP32":
                return parts[2]
            if parts and parts[0] == "RAQIB-ESP32":
                return addr[0]
    except OSError as e:
        log.debug("beacon listen failed: %s", e)
    finally:
        s.close()
    return None


def resolve_host(cfg_host: str | None, timeout_s: float = 6.0) -> str | None:
    """Config address first, then raqib.local, then the robot's broadcast."""
    tries = [h for h in (cfg_host, "raqib.local") if h and h != "auto"]
    for h in tries:
        host, _, port = h.partition(":")
        try:
            socket.getaddrinfo(host, int(port or 80), proto=socket.IPPROTO_TCP)
            if _get_json(h, "/status", timeout=2.5) is not None:
                return h
        except (OSError, ValueError):
            pass
    ip = discover(timeout_s)
    return ip


def _get(host: str, path: str, timeout: float = 2.0, port: int | None = None) -> tuple[int, bytes]:
    h, _, p = host.partition(":")
    conn = http.client.HTTPConnection(h, port or int(p or 80), timeout=timeout)
    try:
        conn.request("GET", path)
        r = conn.getresponse()
        return r.status, r.read()
    finally:
        conn.close()


def _get_json(host: str, path: str, timeout: float = 2.0) -> dict | None:
    try:
        status, body = _get(host, path, timeout)
        return json.loads(body) if status == 200 else None
    except (OSError, ValueError, http.client.HTTPException):
        return None


# ============================================================================ the link
class Esp32Link:
    """One thread talks to the robot 20 times a second: it sends the wheel command (which also keeps the
    firmware's dead-man alive) or asks for the sensors, and keeps the newest status."""

    def __init__(self, host: str, settings: dict | None = None):
        self.host = host
        self.settings = settings or {}
        self.status: dict = {}
        self.status_t = 0.0
        self.target = (0.0, 0.0)
        self._sent = (0.0, 0.0)
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._conn: http.client.HTTPConnection | None = None
        self.errors = 0
        self.on_tick = None             # called about once a second (health refresh)
        self._tick_t = 0.0
        self._was_online = False
        self.push_settings()
        self._thread = threading.Thread(target=self._run, name="esp32-link", daemon=True)
        self._thread.start()

    # -------------------------------------------------------------- http (keep-alive)
    def request(self, path: str, timeout: float = 1.0) -> dict | None:
        h, _, p = self.host.partition(":")
        for attempt in (1, 2):
            try:
                if self._conn is None:
                    self._conn = http.client.HTTPConnection(h, int(p or 80), timeout=timeout)
                self._conn.timeout = timeout
                self._conn.request("GET", path)
                r = self._conn.getresponse()
                body = r.read()
                if r.status != 200:
                    return None
                return json.loads(body)
            except (OSError, ValueError, http.client.HTTPException):
                try:
                    self._conn.close() if self._conn else None
                finally:
                    self._conn = None
                if attempt == 2:
                    return None
        return None

    def push_settings(self) -> dict | None:
        q = "&".join(f"{k}={v}" for k, v in self.settings.items())
        with self._lock:
            return self.request(f"/config?{q}", timeout=2.0) if q else None

    # -------------------------------------------------------------- loop
    def _run(self):
        period = 1.0 / CONTROL_HZ
        while not self._stop.is_set():
            t0 = time.monotonic()
            l, r = self.target
            with self._lock:
                if (l, r) != (0.0, 0.0):
                    st = self.request(f"/drive?l={l:.3f}&r={r:.3f}")
                elif self._sent != (0.0, 0.0):
                    st = self.request("/stop")
                else:
                    st = self.request("/status")
            if st is not None:
                self._sent = (l, r)
                self.status, self.status_t, self.errors = st, time.monotonic(), 0
            else:
                self.errors += 1
            online = self.online
            if online and not self._was_online:
                self.push_settings()    # the robot restarted (or came back): send our settings again
            self._was_online = online
            if self.on_tick and time.monotonic() - self._tick_t > 1.0:
                self._tick_t = time.monotonic()
                try:
                    self.on_tick()
                except Exception as e:  # noqa: BLE001
                    log.debug("health refresh: %s", e)
            self._wake.wait(max(0.0, period - (time.monotonic() - t0)))
            self._wake.clear()

    def drive(self, left: float, right: float):
        new = (round(max(-1.0, min(1.0, left)), 3), round(max(-1.0, min(1.0, right)), 3))
        stopping = new == (0.0, 0.0) and self.target != (0.0, 0.0)
        self.target = new
        if stopping or self._sent == (0.0, 0.0):
            self._wake.set()  # stops and starts go out at once, not at the next tick

    @property
    def online(self) -> bool:
        return time.monotonic() - self.status_t < 1.5

    def get(self, key: str, default=None):
        v = self.status.get(key, default) if self.online else default
        return default if v is None else v

    def close(self):
        self.target = (0.0, 0.0)
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout=1.0)
        with self._lock:
            self.request("/stop")


# ============================================================================ the parts
class Esp32Motors(Motors):
    def __init__(self, link: Esp32Link):
        self.link = link
        self.left = self.right = 0.0
        self.turning = False

    def set_wheels(self, left: float, right: float) -> None:
        self.left, self.right = float(left), float(right)
        if self.turning and (self.left, self.right) == (0.0, 0.0):
            self.cancel_turn()
        self.link.drive(self.left, self.right)

    def cancel_turn(self):
        self.turning = False
        with self.link._lock:
            self.link.request("/stop")

    def turn_by(self, angle_deg: float, power: float, cancel=None, timeout_s: float | None = None) -> str:
        """Turn on the spot on the robot itself (its gyro, 200 Hz): exact even with Wi-Fi delay.
        Returns 'ok', 'timeout', 'cancelled' or 'error'."""
        self.link.drive(0.0, 0.0)
        with self.link._lock:
            st = self.link.request(f"/turn?deg={angle_deg:.2f}&power={power:.3f}", timeout=1.5)
        if not st or st.get("turn") not in ("turning", "done"):
            return "error"
        self.turning = True
        sent = time.monotonic()
        end = sent + (timeout_s or abs(angle_deg) / 30.0 + 5.0)
        try:
            while time.monotonic() < end:
                if cancel is not None and cancel.is_set():
                    self.cancel_turn()
                    return "cancelled"
                if self.link.status_t > sent + 0.02:
                    t = self.link.status.get("turn")
                    if t == "done":
                        return "ok"
                    if t in ("timeout", "stopped", "idle"):
                        return "timeout" if t == "timeout" else "cancelled"
                time.sleep(0.02)
            self.cancel_turn()
            return "timeout"
        finally:
            self.turning = False

    @property
    def applied(self) -> tuple[float, float]:
        """What the wheels really get (the firmware's soft start), for time-based distance."""
        m = self.link.get("motors")
        if isinstance(m, list) and len(m) == 2:
            return float(m[0]), float(m[1])
        return 0.0, 0.0


class FixedCamera(PanTilt):
    """The camera is fixed: the robot turns its whole body to look around."""

    def set_angles(self, pan_deg: float, tilt_deg: float) -> None:
        pass


class Esp32Ultrasonic(Ultrasonics):
    """One HC-SR04P at the front. No echo at all = treat as blocked (forward refused, turning allowed)."""

    def __init__(self, link: Esp32Link):
        self.link = link

    def read_cm(self) -> dict[str, float]:
        ok = self.link.get("us_ok", False)
        d = float(self.link.get("dist_cm", 0.0)) if ok else 0.0
        return {"left": 400.0, "center": d, "right": 400.0}


class NoEncoders(Encoders):
    def ticks(self) -> tuple[int, int]:
        return 0, 0


class Esp32Imu(Imu):
    def __init__(self, link: Esp32Link):
        self.link = link

    def read(self) -> ImuReading:
        g = self.link.get
        return ImuReading(yaw_deg=float(g("yaw", 0.0)), pitch_deg=float(g("pitch", 0.0)), roll_deg=float(g("roll", 0.0)),
                          gyro_z_dps=float(g("gz", 0.0)), accel_g=(float(g("ax", 0.0)), float(g("ay", 0.0)), float(g("az", 1.0))))


class Esp32Env(EnvSensor):
    def __init__(self, link: Esp32Link):
        self.link = link

    def read(self) -> EnvRaw:
        t, rh, p = self.link.get("temp_c"), self.link.get("rh"), self.link.get("press_hpa")
        if t is None:
            raise RuntimeError("AHT20 + BMP280 not answering")
        return EnvRaw(temperature_c=float(t), humidity_pct=float(rh) if rh is not None else float("nan"),
                      pressure_hpa=float(p) if p is not None else float("nan"), gas_resistance_ohm=None, mq135_volts=None)


class Esp32Camera(Camera):
    def __init__(self, host: str):
        self.host = host
        self._last: np.ndarray | None = None

    def capture(self) -> np.ndarray:
        from PIL import Image

        try:
            status, body = _get(self.host, "/capture", timeout=3.0)
            if status == 200 and body[:2] == b"\xff\xd8":
                rgb = np.asarray(Image.open(io.BytesIO(body)).convert("RGB"))
                self._last = np.ascontiguousarray(rgb[:, :, ::-1])     # the HAL hands out BGR
                return self._last
        except (OSError, ValueError, http.client.HTTPException) as e:
            log.debug("capture failed: %s", e)
        if self._last is not None:
            return self._last
        from .real import NullCamera

        return NullCamera().capture()


class Esp32Microphone(Microphone):
    def __init__(self, host: str, port: int = 82):
        self.host, self.port = host, port

    def record(self, seconds: float, sample_rate: int) -> np.ndarray:
        ms = int(max(0.1, min(5.0, seconds)) * 1000)
        try:
            status, body = _get(self.host, f"/audio?ms={ms}", timeout=seconds + 4.0, port=self.port)
            if status != 200:
                raise OSError(f"HTTP {status}")
            with wave.open(io.BytesIO(body)) as w:
                rate = w.getframerate()
                x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)
        except (OSError, ValueError, EOFError, wave.Error, http.client.HTTPException) as e:
            log.warning("microphone: %s", e)
            return np.zeros(int(seconds * sample_rate), np.int16)
        if x.size:
            x -= x.mean()                                     # the PDM microphone has a DC offset
        if rate != sample_rate and x.size:
            n = int(x.size * sample_rate / rate)
            x = np.interp(np.linspace(0, x.size - 1, n), np.arange(x.size), x)
        return np.clip(x, -32768, 32767).astype(np.int16)


class PhoneSpeaker(Speaker):
    """This robot has no speaker: spoken messages go to the phone app (alerts and the Assistant)."""

    present = False

    def say(self, text: str) -> None:
        log.info("[no speaker on the robot] %s", text)


class NoBattery(Battery):
    def read(self) -> BatteryReading:
        return BatteryReading(None, None)


# ============================================================================ factory
def update_health(hw: Hardware, link: Esp32Link) -> None:
    """Refresh the part list from the robot's own status (called by the sensor loop)."""
    if not link.online:
        for part in ("motors", "ultrasonic", "imu", "environment", "camera", "microphone"):
            hw.set_health(part, False, "robot not answering on Wi-Fi", HINTS["link"])
        return
    s = link.status
    ip = s.get("ip", link.host)
    hw.set_health("motors", True, f"DRV8833 + 2 TT motors (2WD) on the ESP32 at {ip}", "")
    checks = {
        "ultrasonic": (s.get("us_ok"), "HC-SR04P at the front, 3.3 V"),
        "imu": (s.get("imu_ok"), "MPU6050 on the ESP32"),
        "environment": (s.get("aht_ok") or s.get("bmp_ok"),
                        "AHT20 + BMP280" if s.get("aht_ok") and s.get("bmp_ok") else ("AHT20 only" if s.get("aht_ok") else "BMP280 only")),
        "camera": (s.get("cam_ok"), "XIAO ESP32S3 Sense camera (OV2640/OV3660)"),
        "microphone": (s.get("mic_ok"), "XIAO ESP32S3 Sense microphone"),
    }
    for part, (ok, detail) in checks.items():
        hw.set_health(part, bool(ok), detail if ok else "not answering", "" if ok else HINTS[part])


def _audio_port(host: str, cfg_port) -> int:
    """The firmware serves audio on port 82; an address with its own port (the emulator) uses that port + 2."""
    if cfg_port not in (None, "auto", ""):
        return int(cfg_port)
    _, _, p = host.partition(":")
    return int(p) + 2 if p else 82


def create_esp32_hardware(cfg: dict) -> Hardware:
    hc = cfg.get("hardware", {})
    want = str(hc.get("esp32_host") or "auto")
    log.info("Looking for the ESP32 robot (%s)...", want)
    host = resolve_host(want, timeout_s=float(hc.get("esp32_discover_s", 8)))
    if not host:
        log.error("ESP32 robot not found. %s", HINTS["link"])
        host = want if want != "auto" else "raqib.local"
    settings = {
        "stop_cm": float(cfg.get("safety", {}).get("stop_distance_cm", 15)),
        "max_duty": float(hc.get("esp32_max_duty", 0.7)),
        "ramp": float(hc.get("motor_ramp_per_s", 4.0)),
        "deadman_ms": int(hc.get("esp32_deadman_ms", 600)),
        "inv_l": int(bool(hc.get("motor_left", {}).get("invert", False))),
        "inv_r": int(bool(hc.get("motor_right", {}).get("invert", False))),
        "min_power": float(cfg.get("motion", {}).get("min_power", 0.3)),
    }
    link = Esp32Link(host, settings)
    t0 = time.monotonic()
    while not link.online and time.monotonic() - t0 < 3.0:
        time.sleep(0.05)
    if link.online:
        log.info("ESP32 robot at %s (firmware %s, Wi-Fi %s)", host, link.status.get("fw"), link.status.get("ssid"))
    hw = Hardware(
        motors=Esp32Motors(link),
        pan_tilt=FixedCamera(),
        ultrasonics=Esp32Ultrasonic(link),
        encoders=NoEncoders(),
        imu=Esp32Imu(link),
        env=Esp32Env(link),
        camera=Esp32Camera(host),
        microphone=Esp32Microphone(host, _audio_port(host, hc.get("esp32_audio_port"))),
        speaker=PhoneSpeaker(),
        battery=NoBattery(),
        simulated=False,
        extra={"esp32": link, "fixed_camera": True, "encoders": False, "build": "esp32", "speaker": False,
               "motor_deadband": float(cfg.get("motion", {}).get("motor_deadband", 0.15))},
    )
    hw.health = {
        "pan_tilt": {"ok": True, "detail": "fixed camera: the robot turns to look around", "hint": ""},
        "encoders": {"ok": True, "detail": "not fitted: distance from motor time + MPU6050 heading", "hint": ""},
        "speaker": {"ok": True, "detail": "no speaker: the phone app speaks and shows alerts", "hint": ""},
        "battery": {"ok": True, "detail": "not measured: ESP32 on a power bank (see its LEDs), motors on 2 x 18650", "hint": ""},
    }
    update_health(hw, link)
    link.on_tick = lambda: update_health(hw, link)
    _orig_close = hw.close

    def _close():
        _orig_close()
        link.close()

    hw.close = _close  # type: ignore[method-assign]
    return hw
