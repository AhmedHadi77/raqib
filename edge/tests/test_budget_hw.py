"""Budget build: AHT20/BMP280 drivers, battery on the ADS1115, and 'looking' by turning the robot (no servos)."""
import math
import time

from robot.hal.real import AHT20, BMP280, AdsBattery, BudgetEnv


class FakeBus:
    """Answers like the real I2C chips for the registers our drivers use."""

    def __init__(self, aht_bytes=None, bmp_calib=None, bmp_data=None):
        self.aht_bytes, self.bmp_calib, self.bmp_data = aht_bytes, bmp_calib, bmp_data
        self.writes = []

    def read_byte(self, addr):
        return 0x18                                  # AHT20 status: calibrated, idle

    def write_i2c_block_data(self, addr, reg, data):
        self.writes.append((addr, reg, list(data)))

    def write_byte_data(self, addr, reg, val):
        self.writes.append((addr, reg, [val]))

    def read_byte_data(self, addr, reg):
        if addr in (0x76, 0x77) and reg == 0xD0 and self.bmp_calib:
            return 0x58
        raise OSError("no device")

    def read_i2c_block_data(self, addr, reg, n):
        if addr == 0x38:
            return self.aht_bytes
        if reg == 0x88:
            return self.bmp_calib
        if reg == 0xF7:
            return self.bmp_data
        raise OSError("no device")


def _aht_bytes(temp_c, rh):
    h = int(rh / 100 * 1048576)
    t = int((temp_c + 50) / 200 * 1048576)
    return [0x18, (h >> 12) & 0xFF, (h >> 4) & 0xFF, ((h & 0xF) << 4) | ((t >> 16) & 0xF), (t >> 8) & 0xFF, t & 0xFF, 0]


def _bmp_calib():
    # the worked example from the Bosch BMP280 datasheet (section 3.12)
    vals = [27504, 26435, -1000, 36477, -10685, 3024, 2855, 140, -7, 15500, -14600, 6000]
    out = []
    for v in vals:
        v &= 0xFFFF
        out += [v & 0xFF, v >> 8]
    return out


def _bmp_data(adc_p=415148, adc_t=519888):
    return [adc_p >> 12, (adc_p >> 4) & 0xFF, (adc_p & 0xF) << 4, adc_t >> 12, (adc_t >> 4) & 0xFF, (adc_t & 0xF) << 4]


def test_aht20_reads_temperature_and_humidity():
    t, h = AHT20(FakeBus(aht_bytes=_aht_bytes(27.5, 61.0))).read()
    assert abs(t - 27.5) < 0.05 and abs(h - 61.0) < 0.05


def test_bmp280_matches_the_datasheet_example():
    p = BMP280(FakeBus(bmp_calib=_bmp_calib(), bmp_data=_bmp_data()), 0x77).read_hpa()
    assert abs(p - 1006.53) < 0.05


def test_budget_env_combines_aht20_bmp280_and_mq135():
    class Ads:
        def read_volts(self, ch):
            return 1.2

    bus = FakeBus(aht_bytes=_aht_bytes(24.0, 55.0), bmp_calib=_bmp_calib(), bmp_data=_bmp_data())
    env = BudgetEnv(bus, {"mq135_divider_gain": 1.5}, Ads())
    r = env.read()
    assert abs(r.temperature_c - 24.0) < 0.1 and abs(r.humidity_pct - 55.0) < 0.1
    assert abs(r.pressure_hpa - 1006.5) < 0.2 and abs(r.mq135_volts - 1.8) < 1e-6 and r.gas_resistance_ohm is None


def test_battery_voltage_through_the_divider():
    class Ads:
        def read_volts(self, ch):
            assert ch == 1
            return 7.6 / 3.13

    r = AdsBattery(Ads(), 1, 3.13, 2).read()
    assert abs(r.voltage - 7.6) < 0.01 and 50 < r.percent < 60


def test_fixed_camera_turns_the_robot_and_back():
    from robot.app import RobotApp
    from robot.config import load_config

    app = RobotApp(load_config(), connect_mqtt=False)
    app.safety.cloud_timeout = 1e9
    w = app.hw.extra["world"]
    try:
        app.hw.extra["fixed_camera"] = True
        with w.lock:
            w.x, w.y, w.theta = 3.0, 0.0, 0.0
        time.sleep(0.3)
        r = app.run_command("pan_tilt", pan=60, tilt=10)
        assert r["status"] == "ok" and r["result"]["fixed_camera"] and r["result"]["pan"] == 60
        with w.lock:
            assert abs(math.degrees(w.theta) - 60) < 12
        r = app.run_command("pan_tilt", pan=0)
        with w.lock:
            assert abs(math.degrees(w.theta)) < 12
    finally:
        app.shutdown()


def test_audio_devices_are_picked_for_the_budget_build(monkeypatch):
    """Webcam mic for input, the Pi's 3.5 mm jack for output (the system default card cannot record)."""
    import subprocess as sp

    from robot.hal import real

    class SD:
        @staticmethod
        def query_devices():
            return [{"name": "bcm2835 Headphones: - (hw:0,0)", "max_input_channels": 0},
                    {"name": "USB 2.0 Camera: Audio (hw:2,0)", "max_input_channels": 1}]

    assert real._pick_microphone(SD, None) == 1
    assert real._pick_microphone(SD, "hw:3,0") == "hw:3,0"
    out = ("card 0: Headphones [bcm2835 Headphones], device 0: bcm2835 Headphones [bcm2835 Headphones]\n"
           "card 1: vc4hdmi0 [vc4-hdmi-0], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0]\n")
    monkeypatch.setattr(real.shutil, "which", lambda n: "/usr/bin/" + n)
    monkeypatch.setattr(real.subprocess, "run", lambda *a, **k: sp.CompletedProcess(a, 0, stdout=out))
    assert real._pick_playback("auto") == "plughw:CARD=Headphones"
    out += "card 3: Device [USB Audio Device], device 0: USB Audio [USB Audio]\n"
    assert real._pick_playback("auto") == "plughw:CARD=Device"


def test_simulator_imitates_the_budget_robot_by_default():
    """sim_build: budget - fixed camera, AHT20 (no VOC) but still an AQI from the MQ-135, 2-cell battery."""
    from robot.app import RobotApp
    from robot.config import load_config

    app = RobotApp(load_config(), connect_mqtt=False)
    app.safety.cloud_timeout = 1e9
    try:
        info = app.info()
        assert info["hardware_profile"] == "budget" and info["fixed_camera"]
        assert "AHT20" in info["health"]["environment"]["detail"]
        raw = app.hw.env.read()
        assert raw.gas_resistance_ohm is None and raw.mq135_volts
        assert 6.0 < app.hw.battery.read().voltage <= 8.4
        env = app.run_command("read_environment", fresh=True)["result"]
        assert env["aqi"] is not None and env["gas_resistance_ohm"] is None
    finally:
        app.shutdown()
    full = RobotApp(load_config(overrides={"sim_build": "full"}), connect_mqtt=False)
    try:
        assert full.info()["hardware_profile"] == "full" and not full.info()["fixed_camera"]
    finally:
        full.shutdown()


def test_wiring_bench_battery_divider_and_webcam():
    """Bench: the battery % needs the 10k/4.7k divider on A1; unplugging the webcam kills camera + microphone."""
    from robot.hal.harness import evaluate
    from robot.wiring_spec import PARTS

    good = {}
    for p in PARTS:
        for pin in p["pins"]:
            s = pin["spec"]
            good[f"{p['id']}.{pin['id']}"] = s.get("ext") or (f"pin:{s['pin']}" if "pin" in s else
                                                               {"p5": "pin:2", "p33": "pin:1", "gnd": "pin:6"}[s["cls"]])
    r = evaluate(good)
    assert r["drivable"] and all(v["ok"] for v in r["health"].values()), r["health"]
    r = evaluate({k: v for k, v in good.items() if not k.startswith("batdiv.")})
    assert not r["health"]["battery"]["ok"] and r["health"]["motors"]["ok"]
    r = evaluate({k: v for k, v in good.items() if k != "cam.usb"})
    assert not r["health"]["camera"]["ok"] and not r["health"]["microphone"]["ok"]
    r = evaluate(dict(good, **{"l298.ena": "pin:35", "l298.enb": "pin:33"}))
    assert not r["health"]["motors"]["ok"]
    r = evaluate(dict(good, **{"l298.12v": "pin:2"}))
    assert r["effects"]["shorts"] and "7.4 V" in r["effects"]["shorts"][0]
