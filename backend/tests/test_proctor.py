"""Exam proctoring + AI settings tests - no robot, broker or AI key needed."""
import asyncio
import base64
import io
import math
import os
import tempfile

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
os.environ.setdefault("EMBEDDING_BACKEND", "hash")

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from PIL import Image  # noqa: E402

from app import ai_settings  # noqa: E402
from app import proctor as P  # noqa: E402
from app.agent.graph import InspectionAgent  # noqa: E402
from app.config import Settings, get_settings  # noqa: E402
from app.mqtt_bridge import RobotState  # noqa: E402
from app.schemas import Ack  # noqa: E402
from app.store import Store  # noqa: E402


def _jpeg() -> str:
    b = io.BytesIO()
    Image.new("RGB", (320, 240), (200, 200, 200)).save(b, "JPEG")
    return base64.b64encode(b.getvalue()).decode()


def _frame(yaw=0.0, pitch=-10.0, objects=()):
    return P.Frame([P.Person(x=0.4, yaw=yaw, pitch=pitch, objects=list(objects), distance_m=1.6)], "sim")


def test_head_turn_needs_to_last():
    tr = P.Tracker(head_turn_deg=35, head_turn_s=3)
    assert tr.update(_frame(yaw=60), now=100) == []
    assert tr.suspicious()
    assert tr.update(_frame(yaw=60), now=101.5) == []
    flags = tr.update(_frame(yaw=60), now=103.2)
    assert [f["type"] for f in flags] == ["head_turn"]
    # a short glance resets
    tr2 = P.Tracker(head_turn_deg=35, head_turn_s=3)
    tr2.update(_frame(yaw=60), now=0)
    tr2.update(_frame(yaw=5), now=1)
    assert tr2.update(_frame(yaw=60), now=3.5) == []


def test_looking_down_and_objects():
    tr = P.Tracker(look_down_deg=40, look_down_s=8)
    for t in range(0, 8):
        assert tr.update(_frame(pitch=-55), now=t) == []
    assert [f["type"] for f in tr.update(_frame(pitch=-55), now=8.5)] == ["looking_down"]
    tr = P.Tracker()
    p = _frame(objects=["cell phone"])
    p.people[0].score = 0.6
    assert tr.update(p, now=0) == []                    # one weak sighting is not enough
    assert [f["type"] for f in tr.update(p, now=1)] == ["phone"]
    assert tr.update(p, now=2) == []                    # not flagged again straight away
    tr = P.Tracker(detect={"objects": False})
    assert tr.update(_frame(objects=["earpiece"]), now=0) == []


def test_head_angles_from_mediapipe_matrix():
    def rot_y(deg):
        a = math.radians(deg)
        return np.array([[math.cos(a), 0, math.sin(a), 0], [0, 1, 0, 0], [-math.sin(a), 0, math.cos(a), 0], [0, 0, 0, 1]])

    def rot_x(deg):
        a = math.radians(deg)
        return np.array([[1, 0, 0, 0], [0, math.cos(a), -math.sin(a), 0], [0, math.sin(a), math.cos(a), 0], [0, 0, 0, 1]])

    assert P.MediaPipeProctor.head_angles(np.eye(4)) == pytest.approx((0, 0), abs=1e-6)
    yaw, pitch = P.MediaPipeProctor.head_angles(rot_y(40))
    assert yaw == pytest.approx(40, abs=0.5) and abs(pitch) < 0.5
    yaw, pitch = P.MediaPipeProctor.head_angles(rot_x(45))     # chin down
    assert pitch == pytest.approx(-45, abs=0.5)


def test_objects_are_given_to_the_nearest_student_and_photo_annotated():
    fr = P.attach_objects(P.Frame([P.Person(x=0.2), P.Person(x=0.7)], "mediapipe",
                                  [{"label": "cell phone", "score": 0.9, "box": (0.66, 0.6, 0.74, 0.7)},
                                   {"label": "laptop", "score": 0.9, "box": (0.1, 0.6, 0.3, 0.7)}]))
    assert fr.people[1].objects == ["cell phone"] and fr.people[0].objects == []
    out = P.annotate(base64.b64decode(_jpeg()), [{"title": "Phone", "x": 0.7, "box": (0.6, 0.3, 0.8, 0.7)}], "caption")
    assert out[:2] == b"\xff\xd8"


class ExamRoomBridge:
    """A robot in an exam room where one student keeps a phone on the desk."""

    def __init__(self):
        self.robots = {"robot01": RobotState("robot01", online=True,
                                             info={"zones": {"Exam_Hall": {"x": 13, "y": 0, "radius": 2}},
                                                   "patrols": {"Exam_Hall": [[11, 0], [15, 0]]},
                                                   "camera": {"hfov_deg": 62.2}},
                                             telemetry={"pose": {"zone": "Exam_Hall"}})}
        self.sent = []
        self.pan = 0.0

    async def send(self, robot_id, action, params=None, timeout=None, issued_by=None, wait=True):
        self.sent.append((action, params))
        await asyncio.sleep(0.01)
        if action == "pan_tilt":
            self.pan = float((params or {}).get("pan", 0))
        res = {"listen_audio": {"label": "quiet_room", "db": 36, "voice_like": False},
               "snapshot": {"image_b64": _jpeg(), "pose": {"x": 11, "y": 0, "heading_deg": 0},
                            "pan_tilt": {"pan": self.pan, "tilt": 0},
                            "sim_truth": {"students": [] if self.pan != 60 else [
                                {"name": "s1", "yaw": 0, "pitch": -48, "objects": ["cell phone"], "distance_m": 1.7,
                                 "bearing_deg": 10, "x_img": 0.34}]}},
               "move": {"traveled_m": 0.6}}.get(action, {})
        return Ack(id="x", action=action, status="ok", result=res)


def test_patrol_flags_a_phone_warns_and_sends_a_photo():
    s = get_settings()
    s.proctor_dwell_s = 1.0
    agent = InspectionAgent(s, ExamRoomBridge(), None, Store(s.data_dir))
    events = []

    async def notify(msg):
        events.append(msg["data"]["event"])

    agent.monitor.notify = notify

    async def scenario():
        await agent.monitor.start("robot01", "Exam_Hall", 5, "normal", "op")
        for _ in range(300):
            await asyncio.sleep(0.05)
            if agent.monitor.session["incidents"]:
                break
        await agent.monitor.stop("test over")

    asyncio.run(scenario())
    sess = agent.monitor.session
    inc = sess["incidents"][0]
    assert inc["type"] == "phone" and inc["warned"] and inc["image"] and inc["close_image"]
    said = [p["text"] for a, p in agent.monitor.make_tools("robot01", "x").bridge.sent if a == "speak"]
    assert any("Please stop cheating" in t for t in said)
    sent = [a for a, _ in agent.monitor.make_tools("robot01", "x").bridge.sent]
    assert "go_to_point" in sent and ("turn", {"angle_deg": 70.0}) in agent.monitor.make_tools("robot01", "x").bridge.sent
    assert "proctor_flag" in events and "monitoring_finished" in events
    saved = agent.store.get_exam_session(sess["id"])
    assert saved and saved["incidents"][0]["type"] == "phone"
    s.proctor_dwell_s = 4.0


def test_ai_settings_write_env_keeps_other_lines(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("ROBOT_ID=robot01\n# LLM\nLLM_PROVIDER=none\n# GOOGLE_API_KEY=\nJWT_SECRET=abc\n", encoding="utf-8")
    monkeypatch.setattr(ai_settings, "ENV_PATH", env)
    s = Settings(_env_file=None)
    vals = ai_settings.apply(s, {"provider": "gemini", "google_api_key": "AIzaSyTESTKEY1234567890"})
    ai_settings.write_env(vals)
    text = env.read_text()
    assert "ROBOT_ID=robot01" in text and "JWT_SECRET=abc" in text
    assert "LLM_PROVIDER=gemini" in text and "GOOGLE_API_KEY=AIzaSyTESTKEY1234567890" in text
    assert "VLM_PROVIDER=gemini" in text and text.count("LLM_PROVIDER=") == 1
    assert s.llm_provider == "gemini" and ai_settings.mask(s.google_api_key).endswith("7890")
    with pytest.raises(ValueError):
        ai_settings.apply(Settings(_env_file=None), {"provider": "openai"})        # no key yet
    with pytest.raises(ValueError):
        ai_settings.apply(Settings(_env_file=None), {"provider": "gemini", "google_api_key": "my key is: x y z"})
