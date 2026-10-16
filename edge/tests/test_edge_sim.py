"""Edge tests in simulation (run:  cd edge && python -m pytest -q)."""
import time

import pytest

from robot.app import RobotApp
from robot.audio_analyzer import audio_features, heuristic_classify
from robot.config import load_config
from robot.environmental_sensor import classify, estimate_aqi


@pytest.fixture(scope="module")
def app():
    a = RobotApp(load_config(overrides={"simulation": True}), connect_mqtt=False)
    a.safety.cloud_timeout = 1e9
    yield a
    a.shutdown()


def test_classifier_matches_proposal():
    cfg = load_config()["environment"]
    assert classify(30.0, 75.0, 50, None, cfg)["comfort_verdict"] == "UNCOMFORTABLE_HOT_HUMID"   # T-05
    assert classify(24.0, 50.0, 165, None, cfg)["gas_verdict"] == "WARNING"                     # T-06 / D2
    assert classify(24.1, 52.0, 38, None, cfg)["overall"] == "COMFORTABLE_SAFE"                 # D3
    assert classify(18.0, 50.0, 30, None, cfg, occupied=False)["comfort_verdict"] == "OVERCOOLED_ENERGY_WASTE"
    assert classify(24.0, 50.0, 350, None, cfg)["gas_verdict"] == "HAZARD"


def test_aqi_estimate_monotonic():
    a_clean = estimate_aqi(50000, 50, 50000)
    a_dirty = estimate_aqi(30000, 50, 50000)
    assert a_clean < 60 < a_dirty


def test_obstacle_stop_T01(app):
    """T-01: robot halts before 15 cm clearance when driving at an obstacle."""
    w = app.hw.extra["world"]
    with w.lock:
        w.x, w.y, w.theta = 6.4, 0.0, 0.0
    app.sensors.reset_pose(6.4, 0.0, 0.0)
    r = app.run_command("move", distance_m=2.0)
    assert r["status"] == "blocked"
    time.sleep(0.2)
    assert app.safety.distances["center"] >= 12.0
    assert app.safety.last_stop_latency_ms < 50
    assert w.collisions == 0


def test_navigation_and_sensing(app):
    w = app.hw.extra["world"]
    with w.lock:
        w.x, w.y, w.theta = 0.0, 0.0, 0.0
    app.sensors.reset_pose()
    r = app.run_command("go_to_zone", zone="IoT_Lab")
    assert r["status"] == "ok", r
    env = app.run_command("read_environment")["result"]
    assert env["comfort_verdict"] == "UNCOMFORTABLE_HOT_HUMID"
    assert env["gas_verdict"] == "NOT_MEASURED"        # the reliable budget build has no gas sensor
    assert app.run_command("listen_audio")["result"]["label"] == "ac_fan"
    snap = app.run_command("snapshot")["result"]
    assert snap["sim_truth"]["zone"] == "IoT_Lab" and len(snap["image_b64"]) > 1000


def test_estop_latched(app):
    assert app.run_command("estop")["status"] == "ok"
    assert app.run_command("move", distance_m=0.2)["status"] == "rejected"
    app.run_command("reset")
    assert app.state.state.value == "IDLE"


def test_privacy_mode_blocks_snapshot(app):
    app.run_command("set_privacy", enabled=True)
    assert app.run_command("snapshot")["status"] == "rejected"
    app.run_command("set_privacy", enabled=False)


@pytest.mark.parametrize("kind", ["quiet_room", "ac_fan", "crowd", "alarm"])
def test_audio_heuristic(kind):
    import numpy as np

    from robot.hal.sim import SimMicrophone

    class W:
        def scenario(self):
            return "x", {"audio": kind}

    s = SimMicrophone(W()).record(1.0, 16000)
    label, _, _ = heuristic_classify(audio_features(s, 16000))
    assert label == kind
    assert isinstance(s, np.ndarray)


def test_real_mode_without_any_parts_starts_safely():
    """Real-hardware mode on a machine with nothing connected: every part is reported, nothing crashes,
    and forward driving is refused because the distance sensors are missing."""
    import time

    from robot.config import load_config
    from robot.hal.real import create_real_hardware
    from robot.app import RobotApp

    cfg = load_config()
    cfg["simulation"] = False
    hw = create_real_hardware(cfg)
    assert {"motors", "ultrasonic", "environment", "camera"} <= set(hw.faults())
    assert all(v["hint"] for k, v in hw.health.items() if not v["ok"] and k != "i2c")
    app = RobotApp(cfg, hw=hw, connect_mqtt=False)
    try:
        time.sleep(0.2)
        r = app.run_command("drive", left=0.5, right=0.5)
        assert r["status"] == "ok" and r["result"]["applied"] == {"left": 0.0, "right": 0.0}
        assert app.run_command("drive", left=-0.5, right=0.5)["result"]["applied"]["left"] == -0.5  # turning allowed
        assert app.run_command("read_environment")["status"] == "error"
        assert app.telemetry()["faults"]
        assert app.info()["health"]["camera"]["ok"] is False
    finally:
        app.shutdown()


def test_sound_scan_faces_the_person_talking():
    """Exam hall: the directional mic + a 360 degree scan points the robot at the student who is talking."""
    import math
    import time

    from robot.app import RobotApp
    from robot.config import load_config

    app = RobotApp(load_config(), connect_mqtt=False)
    app.safety.cloud_timeout = 1e9
    w = app.hw.extra["world"]
    try:
        with w.lock:
            w.x, w.y, w.theta = 13.0, 0.0, 0.0
        # only student_back_left (14.2, 1.35) talks, for the whole scan: a slow test machine must not
        # let the talking schedule switch speakers half way through the 360 degree scan
        w.sources = [dict(src, on_s=1e9, phase_s=0) for src in w.sources if src["name"] == "student_back_left"]
        r = app.run_command("sound_scan", step_deg=45, seconds=0.6)
        assert r["status"] == "ok" and r["result"]["voice_like"]
        with w.lock:
            facing = math.degrees(w.theta)
        assert abs(facing - math.degrees(math.atan2(1.35, 1.2))) < 25, (facing, r["result"]["readings"])   # 45 deg steps, refined
    finally:
        app.shutdown()


def test_exam_hall_patrol_point_students_and_sounds():
    """go_to_point drives the patrol route; the camera reports students in view; a bang is a sudden noise."""
    import time

    from robot.app import RobotApp
    from robot.config import load_config

    app = RobotApp(load_config(), connect_mqtt=False)
    app.safety.cloud_timeout = 1e9
    w = app.hw.extra["world"]
    try:
        assert app.info()["patrols"]["Exam_Hall"]
        with w.lock:
            w.x, w.y, w.theta = 11.0, 0.0, 0.0
        app.sensors.reset_pose(11.0, 0.0, 0.0)
        r = app.run_command("go_to_point", x=12.8, y=0.0, heading_deg=0)
        assert r["status"] == "ok", r
        with w.lock:
            assert abs(w.x - 12.8) < 0.35 and abs(w.y) < 0.35
        app.run_command("pan_tilt", pan=60, tilt=0)
        w.t0 = time.monotonic() - 20                 # back-right student's earpiece behaviour is on (20..65 s)
        snap = app.run_command("snapshot")["result"]
        seen = snap["sim_truth"]["students"]
        assert seen and all(0 <= s["x_img"] <= 1 for s in seen)
        w.t0 = time.monotonic() - 55.3               # dropped pencil case (bang at 55 s)
        a = app.run_command("listen_audio", seconds=1.0)["result"]
        assert a["label"] == "sudden_noise", a
    finally:
        app.shutdown()


def test_webots_mode_explains_when_webots_is_missing(monkeypatch, tmp_path):
    """--webots without Webots installed fails fast with a clear message (no hang)."""
    from robot.config import load_config
    from robot.hal import create_hardware
    from robot.hal import webots as wb

    monkeypatch.setattr(wb, "WEBOTS_HOMES", [str(tmp_path)])
    monkeypatch.setenv("WEBOTS_HOME", str(tmp_path / "nowhere"))
    cfg = load_config(overrides={"simulation": True, "simulator": "webots", "webots": {"connect_timeout_s": 5}})
    assert cfg["zones"]["IoT_Lab"]["view_heading"] == 90
    with pytest.raises(RuntimeError, match="Webots"):
        create_hardware(cfg)


def test_virtual_wiring_controls_the_simulated_robot():
    """Wiring Bench: no wires = dead robot, correct wires = drivable, IN1/IN2 swapped = left side reversed."""
    from robot.app import RobotApp
    from robot.config import load_config
    from robot.wiring_spec import PARTS

    good = {}
    for p in PARTS:
        for pin in p["pins"]:
            s = pin["spec"]
            good[f"{p['id']}.{pin['id']}"] = s.get("ext") or (f"pin:{s['pin']}" if "pin" in s else
                                                               {"p5": "pin:2", "p33": "pin:1", "gnd": "pin:6"}[s["cls"]])
    app = RobotApp(load_config(), connect_mqtt=False)
    app.safety.cloud_timeout = 1e9
    try:
        st = app.run_command("set_wiring", enabled=True, wires={})["result"]
        assert not st["drivable"] and app.hw.health["power"]["ok"] is False
        assert app.run_command("move", distance_m=0.3)["result"].get("traveled_m", 0) < 0.05
        st = app.run_command("set_wiring", enabled=True, wires=good)["result"]
        assert st["drivable"] and st["done"] == st["total"] and not app.hw.faults()
        import time

        time.sleep(0.5)                     # let the safety loop see the distance sensors again
        assert app.run_command("move", distance_m=0.4)["result"]["traveled_m"] > 0.3
        bad = dict(good, **{"l298.in1": "pin:13", "l298.in2": "pin:11"})
        st = app.run_command("set_wiring", enabled=True, wires=bad)["result"]
        assert not st["drivable"] and "backwards" in app.hw.health["motors"]["detail"]
        st = app.run_command("set_wiring", enabled=True, wires=dict(good, **{"imu.gnd": "pin:1"}))["result"]
        assert st["shorts"] and app.hw.health["power"]["ok"] is False
        st = app.run_command("set_wiring", enabled=False)["result"]
        assert not st["enabled"] and app.hw.health["motors"]["ok"]
    finally:
        app.shutdown()


def test_full_build_still_measures_gas():
    """sim_build: full (MQ-135 + BME680 fitted): the VOC source in the IoT Lab gives a gas WARNING."""
    from robot.app import RobotApp
    from robot.config import load_config

    app = RobotApp(load_config(overrides={"sim_build": "full"}), connect_mqtt=False)
    app.safety.cloud_timeout = 1e9
    w = app.hw.extra["world"]
    try:
        z = app.zones["IoT_Lab"]
        with w.lock:
            w.x, w.y, w.theta = float(z["x"]), float(z["y"]), 0.0
        app.sensors.reset_pose(float(z["x"]), float(z["y"]), 0.0)
        env = app.run_command("read_environment", fresh=True)["result"]
        assert env["gas_verdict"] == "WARNING"
    finally:
        app.shutdown()
