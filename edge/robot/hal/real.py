"""Real Raspberry Pi hardware drivers.

Imported ONLY when `simulation: false`, so the project still runs on a laptop
without these libraries. Install them on the Pi with `scripts/install_pi.sh`.

Wiring summary (full table in docs/WIRING.md):
  PCA9685 (I2C 0x40): ch0 -> L298N ENA, ch1 -> L298N ENB, ch14 pan servo, ch15 tilt servo
  L298N IN1/IN2/IN3/IN4 -> GPIO 17/27/22/23
  HC-SR04 left/center/right trig/echo -> GPIO 12/16, 24/25, 20/21  (5V echo -> divider to 3.3V!)
  Encoders -> GPIO 5 (left), 6 (right)
  MPU6050 0x68, BME680 0x76, ADS1115 0x48 (MQ-135 on A0 through a divider), UPS INA219 0x42
"""
from __future__ import annotations

import logging
import math
import shutil
import subprocess
import threading
import time

import numpy as np

from .base import (
    Battery, BatteryReading, Camera, Encoders, EnvRaw, EnvSensor, Hardware, Imu, ImuReading,
    Microphone, Motors, PanTilt, Speaker, Ultrasonics,
)

log = logging.getLogger(__name__)


# =========================================================================== I2C
def _open_bus(bus_no: int):
    from smbus2 import SMBus

    return SMBus(bus_no)


class PCA9685:
    """Minimal PCA9685 16-channel 12-bit PWM driver (smbus2)."""

    MODE1, PRESCALE, LED0_ON_L = 0x00, 0xFE, 0x06

    def __init__(self, bus, address: int = 0x40, freq_hz: float = 50.0):
        self.bus, self.addr = bus, address
        self.lock = threading.Lock()
        self.bus.write_byte_data(self.addr, self.MODE1, 0x00)
        self.set_freq(freq_hz)

    def set_freq(self, freq_hz: float):
        self.freq = float(freq_hz)
        prescale = int(round(25_000_000.0 / (4096.0 * self.freq))) - 1
        with self.lock:
            old = self.bus.read_byte_data(self.addr, self.MODE1)
            self.bus.write_byte_data(self.addr, self.MODE1, (old & 0x7F) | 0x10)  # sleep
            self.bus.write_byte_data(self.addr, self.PRESCALE, prescale)
            self.bus.write_byte_data(self.addr, self.MODE1, old)
            time.sleep(0.005)
            self.bus.write_byte_data(self.addr, self.MODE1, old | 0xA0)  # restart + auto-increment

    def set_raw(self, ch: int, on: int, off: int):
        with self.lock:
            self.bus.write_i2c_block_data(self.addr, self.LED0_ON_L + 4 * ch,
                                          [on & 0xFF, on >> 8, off & 0xFF, off >> 8])

    def set_duty(self, ch: int, duty: float):
        duty = max(0.0, min(1.0, duty))
        if duty <= 0.0:
            self.set_raw(ch, 0, 0x1000)       # full off
        elif duty >= 1.0:
            self.set_raw(ch, 0x1000, 0)       # full on
        else:
            self.set_raw(ch, 0, int(duty * 4095))

    def set_pulse_us(self, ch: int, us: float):
        ticks = int(us * self.freq * 4096 / 1_000_000)
        self.set_raw(ch, 0, max(0, min(4095, ticks)))

    def all_off(self):
        for ch in range(16):
            self.set_duty(ch, 0.0)


def _setup_pin_factory(name: str | None):
    """pigpio = most accurate HC-SR04 timing (needs the pigpiod service), lgpio = works out of the box on
    Raspberry Pi OS Bookworm/Trixie. "auto" tries pigpio first and falls back quietly."""
    if not name:
        return
    try:
        from gpiozero import Device
    except Exception:  # noqa: BLE001
        return
    order = ["pigpio", "lgpio"] if name == "auto" else [name]
    for n in order:
        try:
            if n == "pigpio":
                import pigpio  # noqa: F401
                from gpiozero.pins.pigpio import PiGPIOFactory

                Device.pin_factory = PiGPIOFactory()
            elif n == "lgpio":
                from gpiozero.pins.lgpio import LGPIOFactory

                Device.pin_factory = LGPIOFactory()
            log.info("gpiozero pin factory: %s", n)
            return
        except Exception as e:  # noqa: BLE001
            (log.info if name == "auto" else log.warning)("GPIO pin factory %s not available (%s)", n, e)
    log.warning("Using the gpiozero default pin factory")


# ======================================================================= motors
class RealMotors(Motors):
    """L298N: GPIO direction pins (IN1-IN4) + speed PWM on ENA/ENB, either from a PCA9685 channel or straight
    from a Pi GPIO pin (budget build: no PCA9685, `pwm_pin` in the motor config)."""

    def __init__(self, pca, hw: dict):
        from gpiozero import DigitalOutputDevice, PWMOutputDevice

        self.pca = pca
        self.cfg = {"left": hw["motor_left"], "right": hw["motor_right"]}
        self.pins = {
            side: (DigitalOutputDevice(c["in1"]), DigitalOutputDevice(c["in2"]))
            for side, c in self.cfg.items()
        }
        self.pwm = {}
        if pca is None:
            hz = int(hw.get("motor_pwm_hz", 500))
            for side, c in self.cfg.items():
                if c.get("pwm_pin") is None:
                    raise RuntimeError(f"no PCA9685 and no pwm_pin for motor_{side} in config.yaml")
                self.pwm[side] = PWMOutputDevice(int(c["pwm_pin"]), frequency=hz)
        self.stop()

    def _set(self, side: str, value: float):
        c = self.cfg[side]
        if c.get("invert"):
            value = -value
        a, b = self.pins[side]
        if value > 0:
            a.on(); b.off()
        elif value < 0:
            a.off(); b.on()
        else:
            a.off(); b.off()
        if self.pca is not None:
            self.pca.set_duty(int(c["pwm_channel"]), abs(value))
        else:
            self.pwm[side].value = min(1.0, abs(value))

    def set_wheels(self, left: float, right: float) -> None:
        self._set("left", max(-1.0, min(1.0, left)))
        self._set("right", max(-1.0, min(1.0, right)))

    def close(self) -> None:
        self.stop()
        for a, b in self.pins.values():
            a.close(); b.close()
        for p in self.pwm.values():
            p.close()


class RealPanTilt(PanTilt):
    def __init__(self, pca: PCA9685, hw: dict):
        self.pca, self.pan_cfg, self.tilt_cfg = pca, hw["servo_pan"], hw["servo_tilt"]
        self.set_angles(0, 0)

    @staticmethod
    def _us(cfg: dict, deg: float) -> float:
        deg = max(-90.0, min(90.0, deg))
        lo, hi = float(cfg.get("min_us", 500)), float(cfg.get("max_us", 2400))
        return lo + (deg + 90.0) / 180.0 * (hi - lo)

    def set_angles(self, pan_deg: float, tilt_deg: float) -> None:
        self.pca.set_pulse_us(int(self.pan_cfg["channel"]), self._us(self.pan_cfg, pan_deg))
        self.pca.set_pulse_us(int(self.tilt_cfg["channel"]), self._us(self.tilt_cfg, tilt_deg))

    def close(self) -> None:
        self.pca.set_duty(int(self.pan_cfg["channel"]), 0)
        self.pca.set_duty(int(self.tilt_cfg["channel"]), 0)


# =================================================================== ultrasonic
class RealUltrasonics(Ultrasonics):
    """3x HC-SR04 via gpiozero.DistanceSensor (each runs its own background thread)."""

    def __init__(self, hw: dict):
        from gpiozero import DistanceSensor

        self.sensors = {
            name: DistanceSensor(echo=p["echo"], trigger=p["trigger"], max_distance=4.0,
                                 queue_len=2, partial=True)
            for name, p in hw["ultrasonic"].items()
        }

    def read_cm(self) -> dict[str, float]:
        out = {}
        for name, s in self.sensors.items():
            try:
                d = s.distance
                out[name] = 400.0 if d is None else round(d * 100.0, 1)
            except Exception:  # noqa: BLE001
                out[name] = 400.0
        return out

    def close(self) -> None:
        for s in self.sensors.values():
            s.close()


class RealEncoders(Encoders):
    def __init__(self, hw: dict):
        from gpiozero import DigitalInputDevice

        self._l = self._r = 0
        self._lock = threading.Lock()
        self.left = DigitalInputDevice(hw["encoder_left_pin"], pull_up=True)
        self.right = DigitalInputDevice(hw["encoder_right_pin"], pull_up=True)
        self.left.when_activated = self._inc_l
        self.right.when_activated = self._inc_r

    def _inc_l(self):
        with self._lock:
            self._l += 1

    def _inc_r(self):
        with self._lock:
            self._r += 1

    def ticks(self) -> tuple[int, int]:
        with self._lock:
            return self._l, self._r

    def close(self) -> None:
        self.left.close(); self.right.close()


# ========================================================================== IMU
class RealMPU6050(Imu):
    """MPU6050 over smbus2 with gyro-bias calibration and a complementary filter (50 Hz+)."""

    def __init__(self, bus, address: int = 0x68):
        self.bus, self.addr = bus, address
        self.bus.write_byte_data(self.addr, 0x6B, 0x00)  # wake
        self.bus.write_byte_data(self.addr, 0x1A, 0x03)  # DLPF ~44 Hz
        self.bus.write_byte_data(self.addr, 0x1B, 0x00)  # gyro +-250 dps
        self.bus.write_byte_data(self.addr, 0x1C, 0x00)  # accel +-2 g
        time.sleep(0.1)
        self.bias = self._calibrate()
        self.r = ImuReading()
        self.lock = threading.Lock()
        self._stop = threading.Event()
        threading.Thread(target=self._loop, name="imu", daemon=True).start()

    def _raw(self):
        d = self.bus.read_i2c_block_data(self.addr, 0x3B, 14)

        def s16(i):
            v = (d[i] << 8) | d[i + 1]
            return v - 65536 if v > 32767 else v

        ax, ay, az = s16(0) / 16384.0, s16(2) / 16384.0, s16(4) / 16384.0
        gx, gy, gz = s16(8) / 131.0, s16(10) / 131.0, s16(12) / 131.0
        return ax, ay, az, gx, gy, gz

    def _calibrate(self, n: int = 300):
        log.info("Calibrating MPU6050 gyro - keep the robot still...")
        acc = np.zeros(3)
        for _ in range(n):
            acc += np.array(self._raw()[3:])
            time.sleep(0.003)
        return acc / n

    def _loop(self):
        last = time.monotonic()
        pitch = roll = yaw = 0.0
        while not self._stop.is_set():
            try:
                ax, ay, az, gx, gy, gz = self._raw()
            except OSError:
                time.sleep(0.02)
                continue
            now = time.monotonic()
            dt, last = now - last, now
            gx, gy, gz = gx - self.bias[0], gy - self.bias[1], gz - self.bias[2]
            if abs(gz) < 0.08:
                gz = 0.0  # deadband limits yaw drift
            acc_pitch = math.degrees(math.atan2(-ax, math.hypot(ay, az)))
            acc_roll = math.degrees(math.atan2(ay, az))
            pitch = 0.98 * (pitch + gy * dt) + 0.02 * acc_pitch
            roll = 0.98 * (roll + gx * dt) + 0.02 * acc_roll
            yaw = (yaw + gz * dt + 180.0) % 360.0 - 180.0
            with self.lock:
                self.r = ImuReading(yaw, pitch, roll, gz, (ax, ay, az))
            time.sleep(0.01)

    def read(self) -> ImuReading:
        with self.lock:
            return self.r

    def close(self) -> None:
        self._stop.set()


# ================================================================== environment
class ADS1115:
    def __init__(self, bus, address: int = 0x48):
        self.bus, self.addr = bus, address
        self.lock = threading.Lock()

    def read_volts(self, channel: int) -> float:
        with self.lock:
            return self._read(channel)

    def _read(self, channel: int) -> float:
        cfg = 0x8000 | ((4 + channel) << 12) | (1 << 9) | (1 << 8) | (4 << 5) | 0x03  # +-4.096 V, single shot
        self.bus.write_i2c_block_data(self.addr, 0x01, [cfg >> 8, cfg & 0xFF])
        time.sleep(0.01)
        d = self.bus.read_i2c_block_data(self.addr, 0x00, 2)
        raw = (d[0] << 8) | d[1]
        if raw > 32767:
            raw -= 65536
        return raw * 4.096 / 32768.0


class RealEnv(EnvSensor):
    """BME680 (temp/RH/pressure/gas resistance) + optional MQ-135 through an ADS1115."""

    def __init__(self, bus, hw: dict, ads=None):
        import bme680

        self.s = bme680.BME680(int(hw.get("bme680_address", 0x76)))
        self.s.set_humidity_oversample(bme680.OS_2X)
        self.s.set_pressure_oversample(bme680.OS_4X)
        self.s.set_temperature_oversample(bme680.OS_8X)
        self.s.set_filter(bme680.FILTER_SIZE_3)
        self.s.set_gas_status(bme680.ENABLE_GAS_MEAS)
        self.s.set_gas_heater_temperature(320)
        self.s.set_gas_heater_duration(150)
        self.s.select_gas_heater_profile(0)
        self.last = EnvRaw(25.0, 50.0, 1010.0, None, None)
        self.mq_gain = float(hw.get("mq135_divider_gain", 1.5))
        self.mq_ch = int(hw.get("mq135_channel", 0))
        self.ads = ads

    def read(self) -> EnvRaw:
        if self.s.get_sensor_data():
            d = self.s.data
            gas = d.gas_resistance if d.heat_stable else self.last.gas_resistance_ohm
            mq = None
            if self.ads is not None:
                try:
                    mq = self.ads.read_volts(self.mq_ch) * self.mq_gain
                except OSError:
                    mq = None
            self.last = EnvRaw(d.temperature, d.humidity, d.pressure, gas, mq)
        return self.last


class AHT20:
    """AHT20 / AHT21 temperature + humidity (I2C 0x38). Budget replacement for the BME680."""

    def __init__(self, bus, address: int = 0x38):
        self.bus, self.addr = bus, address
        time.sleep(0.04)
        status = self.bus.read_byte(self.addr)
        if not status & 0x08:                                   # not calibrated yet
            self.bus.write_i2c_block_data(self.addr, 0xBE, [0x08, 0x00])
            time.sleep(0.01)

    def read(self) -> tuple[float, float]:
        self.bus.write_i2c_block_data(self.addr, 0xAC, [0x33, 0x00])
        time.sleep(0.08)
        d = self.bus.read_i2c_block_data(self.addr, 0x00, 7)
        hum = ((d[1] << 12) | (d[2] << 4) | (d[3] >> 4)) / 1048576.0 * 100.0
        temp = (((d[3] & 0x0F) << 16) | (d[4] << 8) | d[5]) / 1048576.0 * 200.0 - 50.0
        return temp, hum


class BMP280:
    """BMP280 pressure (+ temperature) at 0x76/0x77, often on the same board as an AHT20."""

    def __init__(self, bus, address: int = 0x77):
        self.bus, self.addr = bus, address
        if self.bus.read_byte_data(self.addr, 0xD0) not in (0x58, 0x56, 0x57):
            raise RuntimeError("not a BMP280")
        c = self.bus.read_i2c_block_data(self.addr, 0x88, 24)

        def u(i):
            return c[i] | (c[i + 1] << 8)

        def s16(i):
            v = u(i)
            return v - 65536 if v > 32767 else v

        self.t = (u(0), s16(2), s16(4))
        self.p = (u(6),) + tuple(s16(8 + 2 * i) for i in range(8))
        self.bus.write_byte_data(self.addr, 0xF4, 0x57)          # temp x2, pressure x16, normal mode
        self.bus.write_byte_data(self.addr, 0xF5, 0x90)

    def read_hpa(self) -> float:
        d = self.bus.read_i2c_block_data(self.addr, 0xF7, 6)
        adc_p = (d[0] << 12) | (d[1] << 4) | (d[2] >> 4)
        adc_t = (d[3] << 12) | (d[4] << 4) | (d[5] >> 4)
        t1, t2, t3 = self.t
        v1 = (adc_t / 16384.0 - t1 / 1024.0) * t2
        v2 = ((adc_t / 131072.0 - t1 / 8192.0) ** 2) * t3
        t_fine = v1 + v2
        p1, p2, p3, p4, p5, p6, p7, p8, p9 = self.p
        v1 = t_fine / 2.0 - 64000.0
        v2 = v1 * v1 * p6 / 32768.0 + v1 * p5 * 2.0
        v2 = v2 / 4.0 + p4 * 65536.0
        v1 = (p3 * v1 * v1 / 524288.0 + p2 * v1) / 524288.0
        v1 = (1.0 + v1 / 32768.0) * p1
        if v1 == 0:
            return 1013.25
        pres = 1048576.0 - adc_p
        pres = (pres - v2 / 4096.0) * 6250.0 / v1
        v1 = p9 * pres * pres / 2147483648.0
        v2 = pres * p8 / 32768.0
        return (pres + (v1 + v2 + p7) / 16.0) / 100.0


class BudgetEnv(EnvSensor):
    """AHT20 (+ optional BMP280) for temperature / humidity / pressure, MQ-135 through the ADS1115 for air quality."""

    def __init__(self, bus, hw: dict, ads=None):
        self.aht = AHT20(bus, int(hw.get("aht20_address", 0x38)))
        self.bmp = None
        for a in (0x77, 0x76):
            try:
                self.bmp = BMP280(bus, a)
                break
            except Exception:  # noqa: BLE001
                continue
        self.ads = ads
        self.mq_gain = float(hw.get("mq135_divider_gain", 1.5))
        self.mq_ch = int(hw.get("mq135_channel", 0))
        self.last = EnvRaw(25.0, 50.0, 1013.25, None, None)

    def read(self) -> EnvRaw:
        try:
            t, h = self.aht.read()
            p = self.bmp.read_hpa() if self.bmp else 1013.25
            mq = None
            if self.ads is not None:
                try:
                    mq = self.ads.read_volts(self.mq_ch) * self.mq_gain
                except OSError:
                    mq = None
            self.last = EnvRaw(round(t, 2), round(h, 1), round(p, 1), None, mq)
        except OSError:
            pass
        return self.last


class AdsBattery(Battery):
    """Battery voltage through a resistor divider into a spare ADS1115 input (budget build, no UPS gauge)."""

    def __init__(self, ads, channel: int, gain: float, cells: int = 2):
        self.ads, self.ch, self.gain, self.cells = ads, channel, gain, cells

    def read(self) -> BatteryReading:
        try:
            volts = self.ads.read_volts(self.ch) * self.gain
        except OSError:
            return BatteryReading(None, None)
        if volts < 1.0:
            return BatteryReading(None, None)
        pct = max(0.0, min(100.0, (volts / self.cells - 3.3) / 0.9 * 100.0))
        return BatteryReading(round(volts, 2), round(pct, 1))


# ======================================================================= camera
class RealCamera(Camera):
    def __init__(self, cfg: dict):
        c, hw = cfg.get("camera", {}), cfg.get("hardware", {})
        self.size = (int(c.get("width", 640)), int(c.get("height", 480)))
        self.kind = hw.get("camera", "picamera2")
        self.lock = threading.Lock()
        if self.kind == "picamera2":
            try:
                from picamera2 import Picamera2

                self.cam = Picamera2()
                self.cam.configure(self.cam.create_video_configuration(main={"size": self.size, "format": "RGB888"}))
                self.cam.start()
                return
            except Exception as e:  # noqa: BLE001
                log.warning("Picamera2 unavailable (%s) - falling back to OpenCV camera", e)
        import cv2

        self.kind = "opencv"
        self.cam = cv2.VideoCapture(int(hw.get("opencv_camera_index", 0)))
        if not self.cam.isOpened():
            raise RuntimeError("no camera found (Picamera2 and OpenCV both failed)")
        self.cam.set(cv2.CAP_PROP_FRAME_WIDTH, self.size[0])
        self.cam.set(cv2.CAP_PROP_FRAME_HEIGHT, self.size[1])

    def capture(self) -> np.ndarray:
        with self.lock:
            if self.kind == "picamera2":
                return self.cam.capture_array()  # "RGB888" is BGR-ordered => OpenCV ready
            ok, frame = self.cam.read()
            if not ok:
                raise RuntimeError("camera read failed")
            return frame

    def close(self) -> None:
        try:
            if self.kind == "picamera2":
                self.cam.stop()
            else:
                self.cam.release()
        except Exception:  # noqa: BLE001
            pass


def _pick_microphone(sd, device):
    """null/auto = the first USB input (USB mic or the webcam's mic); the Pi's own audio jack cannot record."""
    if device not in (None, "", "auto"):
        return device
    try:
        devs = sd.query_devices()
    except Exception:  # noqa: BLE001
        return None
    for i, d in enumerate(devs):
        if d.get("max_input_channels", 0) > 0 and any(w in d.get("name", "").lower() for w in ("usb", "webcam", "camera", "mic")):
            return i
    return None


def _pick_playback(device):
    """auto = a USB sound card if one is plugged in, else the Pi's 3.5 mm jack ('Headphones'), else the system default."""
    if device not in (None, "", "auto"):
        return device
    aplay = shutil.which("aplay")
    if not aplay:
        return None
    try:
        out = subprocess.run([aplay, "-l"], capture_output=True, text=True, timeout=5).stdout
    except Exception:  # noqa: BLE001
        return None
    import re

    cards = re.findall(r"^card \d+: (\S+) \[([^\]]*)\]", out, re.M)
    for want in ("usb", "headphones"):
        for cid, name in cards:
            if want in (cid + " " + name).lower():
                return f"plughw:CARD={cid}"
    return None


class RealMicrophone(Microphone):
    def __init__(self, device=None):
        import sounddevice as sd

        self.device = _pick_microphone(sd, device)

    def record(self, seconds: float, sample_rate: int) -> np.ndarray:
        import sounddevice as sd

        data = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="int16",
                      device=self.device)
        sd.wait()
        return data[:, 0].copy()


class RealSpeaker(Speaker):
    """espeak-ng voice. With a known output card the sound is piped through aplay to it, so the
    Pi's 3.5 mm jack works even when the system default is HDMI."""

    def __init__(self, tts: str = "espeak-ng", device="auto"):
        self.tts = shutil.which(tts) or shutil.which("espeak")
        self.aplay = shutil.which("aplay")
        self.device = _pick_playback(device) if self.aplay else None

    def say(self, text: str) -> None:
        log.info("[SPEAKER] %s", text)
        if not self.tts:
            return
        if self.device:
            p1 = subprocess.Popen([self.tts, "-s", "150", "--stdout", text], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            subprocess.Popen([self.aplay, "-q", "-D", self.device], stdin=p1.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            p1.stdout.close()
        else:
            subprocess.Popen([self.tts, "-s", "150", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def beep(self, kind: str = "info") -> None:
        f = {"info": 880, "warning": 1320, "alarm": 1760}.get(kind, 880)
        t = np.arange(int(0.2 * 16000)) / 16000
        tone = 0.3 * np.sin(2 * np.pi * f * t)
        if self.device:
            try:
                import io
                import wave

                buf = io.BytesIO()
                with wave.open(buf, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(16000)
                    w.writeframes((tone * 32767).astype("<i2").tobytes())
                p = subprocess.Popen([self.aplay, "-q", "-D", self.device], stdin=subprocess.PIPE,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                p.stdin.write(buf.getvalue())
                p.stdin.close()
                return
            except Exception:  # noqa: BLE001
                pass
        try:
            import sounddevice as sd

            sd.play(tone.astype(np.float32), 16000)
        except Exception:  # noqa: BLE001
            pass


class RealBattery(Battery):
    """INA219 battery monitor found on most Raspberry Pi UPS hats."""

    def __init__(self, bus, address, cells: int = 3):
        self.bus, self.addr, self.cells = bus, address, cells

    def read(self) -> BatteryReading:
        if self.addr is None:
            return BatteryReading(None, None)
        try:
            raw = self.bus.read_word_data(self.addr, 0x02)
            raw = ((raw & 0xFF) << 8) | (raw >> 8)
            volts = (raw >> 3) * 0.004
            pct = max(0.0, min(100.0, (volts / self.cells - 3.0) / 1.2 * 100.0))
            return BatteryReading(round(volts, 2), round(pct, 1))
        except OSError:
            return BatteryReading(None, None)


# ================================================================ missing parts
# When a component is not connected yet (or fails), the robot still starts with a safe
# stand-in and reports the fault in its health list, so you can bring the robot up one
# part at a time.
class NullMotors(Motors):
    def set_wheels(self, left: float, right: float) -> None:
        pass


class NullPanTilt(PanTilt):
    def set_angles(self, pan_deg: float, tilt_deg: float) -> None:
        pass


class NullUltrasonics(Ultrasonics):
    """No distance sensors = assume something is close: forward driving is refused (turning / reverse allowed)."""

    def read_cm(self) -> dict[str, float]:
        return {"left": 0.0, "center": 0.0, "right": 0.0}


class NullEncoders(Encoders):
    def ticks(self) -> tuple[int, int]:
        return 0, 0


class NullImu(Imu):
    def read(self) -> ImuReading:
        return ImuReading()


class NullEnv(EnvSensor):
    def read(self) -> EnvRaw:
        raise RuntimeError("BME680 environment sensor not connected")


class NullCamera(Camera):
    def capture(self) -> np.ndarray:
        from .. import imaging as im

        img = np.full((480, 640, 3), 24, np.uint8)
        im.text(img, "CAMERA NOT CONNECTED", (95, 230), 1.1, (200, 200, 200), 2)
        im.text(img, "check the ribbon cable / config", (120, 270), 0.7, (150, 150, 150), 1)
        return img


class NullBattery(Battery):
    def read(self) -> BatteryReading:
        return BatteryReading(None, None)


class _NullPart(Microphone, Speaker):
    def record(self, seconds, sample_rate):
        return np.zeros(int(seconds * sample_rate), np.int16)

    def say(self, text):
        log.info("[SPEAKER disabled] %s", text)


HINTS = {
    "i2c": "Enable I2C (sudo raspi-config > Interface Options) and check SDA=GPIO2 / SCL=GPIO3 wiring. "
           "Run: python -m hwtest.i2c_scan",
    "motors": "4WD: both motors of a side joined on OUT1/OUT2 (left) and OUT3/OUT4 (right). L298N IN1-IN4 on GPIO 17/27/22/23; ENA/ENB from GPIO 13/19 (budget) or PCA9685 ch0/1. Common ground! "
              "Run: python -m hwtest.test_motors",
    "pan_tilt": "Servos on PCA9685 channels 14/15 with their own 5-6 V supply.",
    "ultrasonic": "HC-SR04 trig/echo pins as in config.yaml, echo through a 1k/2k divider. "
                  "Run: python -m hwtest.test_sensors",
    "encoders": "Encoder OUT on GPIO 5 (left) and 6 (right), 3.3 V supply.",
    "imu": "MPU6050 at 0x68 on I2C. Run: python -m hwtest.i2c_scan",
    "environment": "AHT20 at 0x38 (budget) or BME680 at 0x76/0x77, on the I2C bus. Run: python -m hwtest.test_env",
    "camera": "Pi Camera ribbon cable (blue side to the Ethernet port), sudo apt install python3-picamera2. "
              "Run: python -m hwtest.test_camera_audio",
    "microphone": "USB microphone (or the webcam's mic) plugged in; pip install sounddevice; check with arecord -l.",
    "speaker": "sudo apt install espeak-ng; amplifier + speaker on the Pi's 3.5 mm jack (or a USB sound card); test: speaker-test -D plughw:CARD=Headphones -c1 -t wav",
    "battery": "Battery + through 10k/4.7k divider into ADS1115 A1 (budget), or a UPS gauge (INA219 at ups_ina219_address).",
}


def create_real_hardware(cfg: dict) -> Hardware:
    hw = cfg["hardware"]
    health: dict = {}

    def build(part: str, factory, fallback, detail_ok: str = "connected"):
        try:
            obj = factory()
            health[part] = {"ok": True, "detail": detail_ok, "hint": ""}
            return obj
        except Exception as e:  # noqa: BLE001
            log.error("%s NOT available: %s", part.upper(), e)
            health[part] = {"ok": False, "detail": f"{type(e).__name__}: {e}"[:200], "hint": HINTS.get(part, "")}
            return fallback()

    _setup_pin_factory(hw.get("gpio_pin_factory"))
    bus = build("i2c", lambda: _open_bus(int(hw.get("i2c_bus", 1))), lambda: None, f"bus {hw.get('i2c_bus', 1)}")

    def need_bus():
        if bus is None:
            raise RuntimeError("no I2C bus")
        return bus

    # ---- PWM: PCA9685 board if present (full build), otherwise Pi GPIO pins (budget build)
    pwm_mode = str(hw.get("motor_pwm", "auto")).lower()
    pca = None
    if pwm_mode in ("auto", "pca9685") and bus is not None:
        try:
            pca = PCA9685(bus, int(hw.get("pca9685_address", 0x40)), float(hw.get("pca9685_freq_hz", 50)))
        except Exception as e:  # noqa: BLE001
            if pwm_mode == "pca9685":
                log.error("PCA9685 NOT available: %s", e)
            else:
                log.info("No PCA9685 found - motor speed from GPIO pins, fixed camera (budget build)")
    gpio_pwm_ok = all(hw.get(m, {}).get("pwm_pin") is not None for m in ("motor_left", "motor_right"))
    if pca is not None:
        motors = build("motors", lambda: RealMotors(pca, hw), NullMotors, "L298N, speed from PCA9685")
    elif pwm_mode != "pca9685" and gpio_pwm_ok:
        pins = f"{hw['motor_left']['pwm_pin']}/{hw['motor_right']['pwm_pin']}"
        motors = build("motors", lambda: RealMotors(None, hw), NullMotors, f"L298N, speed from GPIO {pins}")
    else:
        motors = NullMotors()
        health["motors"] = {"ok": False, "detail": "PCA9685 not found and no pwm_pin set", "hint": HINTS["motors"]}

    fixed_camera = False
    pt_mode = str(hw.get("pan_tilt", "auto")).lower()
    if pca is not None and pt_mode != "none":
        pan_tilt = build("pan_tilt", lambda: RealPanTilt(pca, hw), NullPanTilt, "servos on PCA9685 ch14/15")
    elif pt_mode in ("auto", "none"):
        pan_tilt, fixed_camera = NullPanTilt(), True
        health["pan_tilt"] = {"ok": True, "detail": "fixed camera: the robot turns to look around", "hint": ""}
    else:
        pan_tilt = NullPanTilt()
        health["pan_tilt"] = {"ok": False, "detail": "PCA9685 not available", "hint": HINTS["pan_tilt"]}

    ultrasonics = build("ultrasonic", lambda: RealUltrasonics(hw), NullUltrasonics, "3x HC-SR04")
    encoders = build("encoders", lambda: RealEncoders(hw), NullEncoders, "GPIO 5 / 6")
    imu = build("imu", lambda: RealMPU6050(need_bus(), int(hw.get("mpu6050_address", 0x68))), NullImu, "MPU6050")

    # ---- ADC (shared by the MQ-135 and the battery voltage)
    ads = None
    if bus is not None and hw.get("ads1115_address") is not None:
        try:
            ads = ADS1115(bus, int(hw["ads1115_address"]))
            ads.read_volts(int(hw.get("mq135_channel", 0)))
        except OSError:
            log.warning("ADS1115 not found - no MQ-135 gas value and no battery voltage")
            ads = None

    # ---- climate: BME680 (full build) or AHT20 (+BMP280) (budget build)
    env_mode = str(hw.get("env_sensor", "auto")).lower()
    env = None
    errors = []
    for kind in (["bme680", "aht20"] if env_mode == "auto" else [env_mode]):
        try:
            if kind == "bme680":
                env = RealEnv(need_bus(), hw, ads)
                detail = "BME680"
            else:
                env = BudgetEnv(need_bus(), hw, ads)
                detail = "AHT20" + (" + BMP280" if env.bmp else "")
            detail += " + MQ-135 (ADS1115)" if ads else " (no MQ-135 / ADS1115)"
            health["environment"] = {"ok": True, "detail": detail, "hint": ""}
            break
        except Exception as e:  # noqa: BLE001
            errors.append(f"{kind}: {type(e).__name__}: {e}")
    if env is None:
        env = NullEnv()
        health["environment"] = {"ok": False, "detail": "; ".join(errors)[:200], "hint": HINTS["environment"]}

    camera = build("camera", lambda: RealCamera(cfg), NullCamera, hw.get("camera", "picamera2"))
    mic = build("microphone", lambda: RealMicrophone(hw.get("microphone_device")), _NullPart, "sounddevice")
    speaker = RealSpeaker(hw.get("speaker_tts", "espeak-ng"), hw.get("speaker_device", "auto"))
    health["speaker"] = {"ok": bool(speaker.tts), "detail": speaker.tts or "espeak-ng not installed",
                         "hint": "" if speaker.tts else HINTS["speaker"]}

    # ---- battery: UPS gauge (INA219) if it answers, else voltage divider into the ADS1115
    battery = None
    if bus is not None and hw.get("ups_ina219_address") is not None:
        b = RealBattery(bus, int(hw["ups_ina219_address"]), int(hw.get("battery_cells", 3)))
        if b.read().voltage is not None:
            battery = b
            health["battery"] = {"ok": True, "detail": "UPS gauge (INA219)", "hint": ""}
    if battery is None and ads is not None and hw.get("battery_adc_channel") is not None:
        b = AdsBattery(ads, int(hw["battery_adc_channel"]), float(hw.get("battery_divider_gain", 3.13)),
                       int(hw.get("battery_adc_cells", 2)))
        if b.read().voltage is not None:
            battery = b
            health["battery"] = {"ok": True, "detail": f"battery voltage on ADS1115 A{hw['battery_adc_channel']}", "hint": ""}
    if battery is None:
        battery = NullBattery()
        health["battery"] = {"ok": False, "detail": "no battery gauge answering", "hint": HINTS["battery"]}

    parts = Hardware(
        motors=motors, pan_tilt=pan_tilt, ultrasonics=ultrasonics, encoders=encoders, imu=imu, env=env,
        camera=camera, microphone=mic, speaker=speaker, battery=battery,
        simulated=False, extra={"pca": pca, "bus": bus, "fixed_camera": fixed_camera}, health=health,
    )
    faults = parts.faults()
    if faults:
        log.warning("Robot started with missing parts: %s (see the app's Robot health screen)", ", ".join(faults))
    _orig = parts.close

    def _close():
        _orig()
        try:
            if pca:
                pca.all_off()
            if bus:
                bus.close()
        except Exception:  # noqa: BLE001
            pass

    parts.close = _close  # type: ignore[method-assign]
    return parts
