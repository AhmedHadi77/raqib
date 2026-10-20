"""ESP32 robot 3.0: the PC program drives the robot over Wi-Fi through the real driver (robot/hal/esp32.py),
talking to tools/esp32_emulator.py, which answers exactly like the firmware (same API and safety rules)."""
from __future__ import annotations

import math
import re
import socket
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture()
def robot():
    import esp32_emulator as E
    from robot.app import RobotApp
    from robot.config import load_config

    port, aport = _free_port(), _free_port()
    dev, servers = E.serve(port, aport)
    cfg = load_config(overrides={"simulation": False, "motion": {"motor_deadband": 0.0},
                                 "hardware": {"board": "esp32", "esp32_host": f"127.0.0.1:{port}", "esp32_audio_port": aport}})
    app = RobotApp(cfg, connect_mqtt=False)
    app.safety.cloud_timeout = 1e9
    try:
        yield app, dev
    finally:
        app.shutdown()
        for s in servers:
            s.shutdown()
        dev.close()


def _truth(dev):
    with dev.w.lock:
        return dev.w.x, dev.w.y, math.degrees(dev.w.theta)


def test_esp32_robot_parts_and_profile(robot):
    app, dev = robot
    info = app.info()
    assert info["hardware_profile"] == "esp32" and info["fixed_camera"] and info["speaker"] is False
    assert not app.hw.faults(), app.hw.health
    assert "no speaker" in app.hw.health["speaker"]["detail"]
    assert app.hw.ultrasonics.read_cm()["left"] == 400.0          # one sensor, at the front


def test_esp32_moves_and_turns_accurately(robot):
    app, dev = robot
    x0, y0, _ = _truth(dev)
    r = app.run_command("move", distance_m=1.0)
    assert r["status"] == "ok"
    time.sleep(0.3)
    x1, y1, _ = _truth(dev)
    assert abs(math.hypot(x1 - x0, y1 - y0) - 1.0) < 0.05
    for angle in (90, -90, 180):
        h0 = _truth(dev)[2]
        r = app.run_command("turn", angle_deg=angle)
        assert r["status"] == "ok"
        time.sleep(0.3)
        change = (_truth(dev)[2] - h0 + 180) % 360 - 180
        assert abs(abs(change) - abs(angle)) < 5 and (change > 0) == (angle > 0) or abs(angle) == 180
        assert abs(((app.sensors.heading - _truth(dev)[2]) + 180) % 360 - 180) < 2     # the estimate follows the truth


def test_esp32_sensors_camera_and_microphone(robot):
    app, _ = robot
    env = app.run_command("read_environment", fresh=True)["result"]
    assert env["temperature_c"] > 0 and env["pressure_hpa"] > 900 and env["gas_verdict"] == "NOT_MEASURED"
    snap = app.run_command("snapshot")["result"]
    assert snap["width"] > 0 and len(snap["image_b64"]) > 1000
    audio = app.run_command("listen_audio", seconds=1.0)["result"]
    assert audio["db"] > 0
    assert app.run_command("speak", text="hello")["result"]["spoken"] is False


def test_esp32_firmware_stops_before_an_obstacle(robot):
    """The emulated firmware refuses to drive forward under 15 cm even if the PC keeps asking."""
    app, dev = robot
    with dev.w.lock:                                   # put the robot 0.4 m in front of the corridor's end wall
        x1 = dev.w.bounds[2]
        dev.w.x, dev.w.y, dev.w.theta = x1 - 0.4 - 0.12, 0.0, 0.0
    app.sensors.reset_pose(x1 - 0.52, 0.0, 0.0)
    blocked = False
    end = time.monotonic() + 4.0
    while time.monotonic() < end:
        app.hw.motors.set_wheels(0.5, 0.5)            # straight to the hardware: bypasses the PC's own safety
        blocked = blocked or dev.blocked
        time.sleep(0.05)
    app.hw.motors.set_wheels(0.0, 0.0)
    time.sleep(0.2)
    assert blocked and 10.0 <= dev.dist <= 20.0       # it drove up to the wall and stopped about 15 cm short
    with dev.w.lock:
        assert dev.w.collisions == 0


def test_esp32_deadman_stops_when_the_pc_goes_quiet(robot):
    app, dev = robot
    app.hw.extra["esp32"]._stop.set()                 # the PC program "freezes": no more commands
    time.sleep(0.2)
    with dev.lock:
        dev.tgt = [0.6, 0.6]
        dev.last_cmd = time.monotonic()
    time.sleep(1.0)                                   # > 0.6 s dead-man
    assert dev.out == [0.0, 0.0]


def test_no_robot_on_wifi_starts_safely():
    """ESP32 switched off: the program still starts, shows the fault, and refuses to drive forward."""
    from robot.app import RobotApp
    from robot.config import load_config

    port = _free_port()
    cfg = load_config(overrides={"simulation": False, "hardware": {"board": "esp32", "esp32_host": f"127.0.0.1:{port}",
                                                                   "esp32_discover_s": 0.5}})
    app = RobotApp(cfg, connect_mqtt=False)
    try:
        assert "motors" in app.hw.faults() and "robot not answering" in app.hw.health["motors"]["detail"]
        assert app.hw.ultrasonics.read_cm()["center"] == 0.0
    finally:
        app.shutdown()


def test_firmware_matches_the_wiring_spec():
    """The pins in the firmware are the pins on the Wiring Bench, in the docs and in the driver's hints."""
    from robot.wiring_spec import PARTS

    src = (ROOT / "esp32" / "raqib_esp32" / "raqib_esp32.ino").read_text(encoding="utf-8")
    gpio = {int(a): int(b) for a, b in re.findall(r"D(\d+) \(GPIO(\d+)\)", src)}
    assert gpio == {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 43, 7: 44}
    assert "PIN_AIN1 = 1, PIN_AIN2 = 2" in src and "PIN_BIN1 = 3, PIN_BIN2 = 4" in src
    assert "PIN_SDA = 5, PIN_SCL = 6" in src and "PIN_TRIG = 43, PIN_ECHO = 44" in src
    why = " ".join(pin["why"] for p in PARTS for pin in p["pins"])
    for d in ("D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7"):
        assert d in why
    for path in ("/status", "/drive", "/stop", "/turn", "/config", "/capture", "/audio"):
        assert f'"{path}"' in src
