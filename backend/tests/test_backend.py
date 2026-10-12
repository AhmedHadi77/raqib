"""Backend unit tests - no broker or robot needed.   cd backend && python -m pytest -q"""
import asyncio
import os
import tempfile

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
os.environ.setdefault("EMBEDDING_BACKEND", "hash")

import pytest  # noqa: E402

from app.agent.graph import InspectionAgent  # noqa: E402
from app.agent.planner import find_zones, rule_plan  # noqa: E402
from app.auth import authenticate, create_token, decode_token  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.memory import SemanticMemory, infer_filters  # noqa: E402
from app.mqtt_bridge import RobotState  # noqa: E402
from app.report import fuse  # noqa: E402
from app.schemas import Ack, VisionAnalysis  # noqa: E402
from app.store import Store  # noqa: E402
from app.vlm import ground  # noqa: E402

ZONES = ["Home", "IoT_Lab", "LectureHall_B", "LectureHall_A"]


def test_zone_matching():
    assert find_zones("inspect the IoT laboratory and lecture hall b", ZONES) == ["IoT_Lab", "LectureHall_B"]
    assert find_zones("go to hall A", ZONES) == ["LectureHall_A"]


def test_rule_planner():
    assert rule_plan("patrol all rooms", ZONES)[0] == {"tool": "inspect_zone", "args": {"zone": "IoT_Lab"}}
    assert rule_plan("Show me all rooms where the air quality was unhealthy last month", ZONES)[0]["tool"] == "search_history"
    assert rule_plan("move back 30 cm", ZONES) == [{"tool": "move", "args": {"distance_m": -0.3}}]
    assert rule_plan("turn right 45", ZONES) == [{"tool": "turn", "args": {"angle_deg": -45.0}}]
    assert rule_plan("stop", ZONES) == [{"tool": "stop", "args": {}}]


@pytest.mark.parametrize("msg,expected", [
    ("check the aircon in hall B", [("check_ac", {"zone": "LectureHall_B"})]),
    ("is the AC working?", [("check_ac", {})]),
    ("what did you find", [("last_findings", {})]),
    ("go to the lab", [("go_to_zone", {"zone": "IoT_Lab"})]),
    ("move forward one meter", [("move", {"distance_m": 1.0})]),
    ("move left 50 cm", [("turn", {"angle_deg": 90.0}), ("move", {"distance_m": 0.5})]),
    ("turn around", [("turn", {"angle_deg": 180.0})]),
    ("look up", [("pan_tilt", {"pan": 0, "tilt": 35})]),
    ("is anyone in hall A?", [("go_to_zone", {"zone": "LectureHall_A"}), ("capture_and_analyze", {"focus": "people"})]),
    ("come back", [("return_home", {})]),
    ("go 500 meter and take picture and tell me what it is",
     [("move", {"distance_m": 500.0}), ("capture_and_analyze", {"focus": "describe: tell me what it is"})]),
    ("what do you see in front of you", [("capture_and_analyze", {"focus": "describe: what do you see in front of you"})]),
    ("check who is speaking", [("find_sound", {"warn": False})]),
    ("go near the sounds and tell them to stop talking", [("find_sound", {"warn": True})]),
    ("stop monitoring", [("stop_monitoring", {})]),
    ("how is the exam going?", [("monitor_status", {})]),
    ("turn left, go forward 2 meters, look up and take a photo, then come back",
     [("turn", {"angle_deg": 90.0}), ("move", {"distance_m": 2.0}), ("pan_tilt", {"pan": 0, "tilt": 35}),
      ("capture_and_analyze", {"focus": "describe: take a photo"}), ("return_home", {})]),
])
def test_voice_style_commands(msg, expected):
    assert [(s["tool"], s["args"]) for s in rule_plan(msg, ZONES)] == expected


def test_go_there_uses_context():
    assert rule_plan("go there", ZONES, context_zone="LectureHall_B") == [{"tool": "go_to_zone", "args": {"zone": "LectureHall_B"}}]


def test_fusion_sample_report_D2():
    v = VisionAnalysis(occupants=0, lights_on=True, projector_on=True, exit_clear=False, extinguisher_present=True,
                       confidence=0.9)
    env = {"temperature_c": 29.4, "humidity_pct": 74, "aqi": 165, "aqi_label": "Unhealthy", "gas_verdict": "WARNING"}
    z = fuse("IoT_Lab", v, env, {"label": "ac_fan", "db": 68})
    types = {a.type for a in z.anomalies}
    assert {"energy_waste", "comfort", "air_quality", "blocked_exit"} <= types
    assert z.comfort_verdict == "UNCOMFORTABLE_HOT_HUMID" and not z.compliant
    assert z.energy_status == "WASTE" and z.safety_status == "HAZARD"


def test_fusion_all_clear_D3():
    v = VisionAnalysis(occupants=0, extinguisher_present=True, confidence=0.9)
    env = {"temperature_c": 24.1, "humidity_pct": 52, "aqi": 38, "aqi_label": "Good", "gas_verdict": "NORMAL"}
    z = fuse("LectureHall_A", v, env, {"label": "quiet_room", "db": 35})
    assert z.compliant and not z.anomalies


def test_grounding_flags_dark_image():
    va = ground(VisionAnalysis(lights_on=True, confidence=0.9), {"mean_brightness": 10})
    assert va.needs_human_review


def test_auth_roundtrip():
    assert authenticate("admin", "admin123") == "admin"
    assert authenticate("admin", "wrong") is None
    tok, _ = create_token("bob", "operator")
    assert decode_token(tok)["role"] == "operator"


def test_memory_search_filters():
    f = infer_filters("Show me all rooms where the air quality was unhealthy last month", ZONES)
    assert f["gas_verdict"] == ["WARNING", "HAZARD"] and f["days"] == 31
    m = SemanticMemory(get_settings())
    m.seed(40)
    res = m.search("rooms with unhealthy air quality last month", k=3)
    assert res["results"]
    assert all(h["metadata"]["gas_verdict"] in ("WARNING", "HAZARD") for h in res["results"])


class FakeBridge:
    """Pretends to be the robot: answers commands with canned sensor data."""

    def __init__(self):
        self.robots = {"robot01": RobotState("robot01", online=True, info={"zones": {z: {} for z in ZONES}},
                                             telemetry={"pose": {"zone": "Home"}})}
        self.sent = []

    async def send(self, robot_id, action, params=None, timeout=None, issued_by=None, wait=True):
        self.sent.append(action)
        res = {
            "go_to_zone": {"zone": (params or {}).get("zone")},
            "snapshot": {"image_b64": "aGVsbG8=", "mean_brightness": 150, "zone": "IoT_Lab",
                         "sim_truth": {"zone": "IoT_Lab", "occupants": 0, "lights_on": True, "exit_blocked": True}},
            "read_environment": {"temperature_c": 30.0, "humidity_pct": 75, "aqi": 170, "aqi_label": "Unhealthy",
                                 "gas_verdict": "WARNING", "comfort_verdict": "UNCOMFORTABLE_HOT_HUMID"},
            "listen_audio": {"label": "ac_fan", "title": "Active Air-Conditioner / Exhaust Fan", "db": 68,
                             "confidence": 0.8},
        }.get(action, {})
        return Ack(id="x", action=action, status="ok", result=res)


def test_agent_end_to_end_with_fake_robot():
    s = get_settings()
    bridge = FakeBridge()
    agent = InspectionAgent(s, bridge, None, Store(s.data_dir))
    events = []

    async def emit(ev):
        events.append(ev["type"])

    resp = asyncio.run(agent.run("Inspect the IoT lab", "robot01", "tester", emit))
    assert resp.report_id and "IoT Lab" in resp.reply
    assert resp.speech.startswith("I've finished") and "**" not in resp.speech
    assert "go_to_zone" in bridge.sent and "snapshot" in bridge.sent
    assert "plan" in events and "done" in events
    assert agent.store.get_report(resp.report_id).zones[0].safety_status == "HAZARD"


@pytest.mark.parametrize("msg", ["hello", "what can you do"])
def test_agent_help_reply(msg):
    s = get_settings()
    agent = InspectionAgent(s, FakeBridge(), None, Store(s.data_dir))
    resp = asyncio.run(agent.run(msg, "robot01"))
    assert "Inspect" in resp.reply and resp.speech


def test_check_ac_and_findings_spoken():
    s = get_settings()
    bridge = FakeBridge()
    agent = InspectionAgent(s, bridge, None, Store(s.data_dir))
    resp = asyncio.run(agent.run("check the aircon in the IoT lab", "robot01", "op"))
    assert "running" in resp.reply and "isn't cooling well" in resp.reply, resp.reply
    assert resp.ack and "air-conditioning" in resp.ack
    assert resp.images and "![photo]" in resp.reply
    asyncio.run(agent.run("inspect the IoT lab", "robot01", "op"))
    resp = asyncio.run(agent.run("what did you find?", "robot01", "op"))
    assert "IoT Lab had" in resp.reply and resp.report_id
    # "go there" remembers the room talked about last
    resp = asyncio.run(agent.run("go there", "robot01", "op"))
    assert resp.steps[0].args == {"zone": "IoT_Lab"}


def test_user_accounts_and_schedules(tmp_path):
    st = Store(str(tmp_path))
    st.seed_users({"admin": ("admin123", "admin"), "op": ("op12345", "operator")})
    st.seed_users({"other": ("x", "viewer")})                       # only seeds once
    assert {u["username"] for u in st.list_users()} == {"admin", "op"}
    u = st.get_user("op")
    assert u["pw"].startswith("pbkdf2$") and st.check_password("op12345", u["pw"])
    st.update_user("op", password="newpass1", disabled=True)
    assert st.check_password("newpass1", st.get_user("op")["pw"]) and st.get_user("op")["disabled"]
    sc = st.save_schedule({"name": "Morning", "command": "Patrol all rooms", "time": "07:45", "days": [0, 2]}, "admin")
    assert sc["days"] == [0, 2] and sc["enabled"]
    st.set_schedule_enabled(sc["id"], False)
    assert not st.get_schedule(sc["id"])["enabled"]


def test_real_camera_without_vision_model_does_not_invent_findings():
    """No VLM + real camera (no simulator truth): no fake 'empty room' energy findings."""
    s = get_settings()
    bridge = FakeBridge()
    orig = bridge.send

    async def send(robot_id, action, params=None, **kw):
        ack = await orig(robot_id, action, params, **kw)
        if action == "snapshot":
            ack.result = {"image_b64": "aGVsbG8=", "mean_brightness": 150, "zone": "IoT_Lab"}  # real camera
        return ack

    bridge.send = send
    agent = InspectionAgent(s, bridge, None, Store(s.data_dir))
    resp = asyncio.run(agent.run("inspect the IoT lab", "robot01"))
    rep = agent.store.get_report(resp.report_id)
    types = {a.type for a in rep.zones[0].anomalies}
    assert "energy_waste" not in types and "blocked_exit" not in types
    assert {"comfort", "air_quality"} <= types          # sensors still report what they measured
    resp = asyncio.run(agent.run("is anyone in the lab?", "robot01"))
    assert "no vision AI" in resp.reply


def test_exam_monitoring_command_and_guard():
    zs = ZONES + ["Exam_Hall"]
    assert rule_plan("monitor the exam in the exam hall for 90 minutes", zs) == [
        {"tool": "start_monitoring", "args": {"minutes": 90.0, "sensitivity": "normal", "zone": "Exam_Hall"}}]
    s = get_settings()
    agent = InspectionAgent(s, FakeBridge(), None, Store(s.data_dir))

    async def scenario():
        async def never_ends(*_a, **_k):
            await asyncio.sleep(3600)

        agent.monitor._run = never_ends            # keep the session "running" without a robot loop
        await agent.monitor.start("robot01", "IoT_Lab", 30, "normal", "op")
        busy = await agent.run("go to hall A", "robot01", "op")
        status = await agent.run("how is the exam going?", "robot01", "op")
        stopped = await agent.run("stop monitoring", "robot01", "op")
        return busy, status, stopped

    busy, status, stopped = asyncio.run(scenario())
    assert "monitoring the exam" in busy.reply and not busy.steps
    assert "I'm monitoring IoT Lab" in status.reply
    assert "stopped" in stopped.reply.lower() and not agent.monitor.active
