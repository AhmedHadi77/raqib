"""Exam proctoring vision: who is looking away, who has a phone, notes or an earpiece.

Three ways to look at a camera frame, best available first:
  sim        - the simulator says exactly what each student is doing (free, for testing the whole flow)
  mediapipe  - on this PC: MediaPipe Face Landmarker (head yaw / pitch for up to 12 faces) and
               Object Detector (EfficientDet, 'cell phone' and 'book'); runs offline in ~50 ms a frame
  vision AI  - Gemini / GPT-4o / Ollama (if configured): also spots notes / cheat sheets and earpieces,
               which no small offline model recognises reliably

A Tracker turns single frames into fair flags: a head turn counts only when it lasts `head_turn_s`
seconds, looking down only after `look_down_s`, and an object only when it is seen in two frames
(or once with high confidence). The robot never identifies anyone: tracks are anonymous seats.
"""
from __future__ import annotations

import base64
import io
import logging
import math
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .agent.llm import extract_json, message_text

log = logging.getLogger(__name__)

FLAGS = {
    "phone": {"title": "Phone", "say": "Please stop cheating. Put your phone away now, phones are not allowed in this exam."},
    "notes": {"title": "Notes or cheat sheet", "say": "Please stop cheating. Put those notes away, they are not allowed in this exam."},
    "earpiece": {"title": "Earpiece", "say": "Please stop cheating. Remove your earpiece, it is not allowed in this exam."},
    "head_turn": {"title": "Looking at someone else's paper", "say": "Please keep your eyes on your own paper."},
    "looking_down": {"title": "Looking down for a long time", "say": "Please keep your eyes on your exam paper and your hands on the desk."},
    "talking": {"title": "Talking", "say": "Please stop talking. This is an exam."},
    "whisper": {"title": "Whispering", "say": "Please stop whispering. This is an exam."},
    "noise": {"title": "Sudden noise", "say": None},
}
OBJECT_FLAGS = {"cell phone": "phone", "mobile phone": "phone", "phone": "phone", "smartphone": "phone",
                "notes": "notes", "cheat sheet": "notes", "paper notes": "notes", "book": "notes",
                "earpiece": "earpiece", "earbud": "earpiece", "earbuds": "earpiece", "headphones": "earpiece"}

MODEL_URLS = {
    "face_landmarker.task": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
    "efficientdet_lite0.tflite": "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float32/1/efficientdet_lite0.tflite",
}


@dataclass
class Person:
    x: float                      # horizontal centre in the image, 0 = left .. 1 = right
    yaw: float | None = None      # head turn, degrees (0 = facing their desk / the camera)
    pitch: float | None = None    # head tilt, degrees (negative = looking down)
    objects: list[str] = field(default_factory=list)
    box: tuple[float, float, float, float] | None = None   # normalised x0, y0, x1, y1
    distance_m: float | None = None
    bearing_deg: float = 0.0      # left (+) / right (-) of the camera axis
    score: float = 0.9


@dataclass
class Frame:
    people: list[Person]
    source: str
    objects: list[dict] = field(default_factory=list)   # [{label, score, box}] not tied to a face


# ============================================================================ providers
def from_sim(snapshot: dict) -> Frame | None:
    truth = snapshot.get("sim_truth") or {}
    if truth.get("webcam") or "students" not in truth:
        return None
    people = []
    for st in truth["students"]:
        x = float(st["x_img"])
        w = max(0.05, min(0.25, 0.3 / max(st["distance_m"], 0.5)))
        people.append(Person(x=x, yaw=float(st["yaw"]), pitch=float(st["pitch"]), objects=list(st["objects"]),
                             box=(max(0, x - w / 2), 0.36, min(1, x + w / 2), 0.68), distance_m=st["distance_m"],
                             bearing_deg=float(st["bearing_deg"])))
    return Frame(people, "sim")


class MediaPipeProctor:
    """Offline face + object analysis on this PC (pip install mediapipe; models download once)."""

    def __init__(self, models_dir: str, hfov_deg: float = 62.2, pitch_sign: float = 1.0):
        self.dir = Path(models_dir)
        self.hfov = hfov_deg
        self.pitch_sign = pitch_sign
        self.face = self.det = None
        self.error: str | None = None

    @staticmethod
    def available() -> bool:
        try:
            import mediapipe  # noqa: F401

            return True
        except Exception:  # noqa: BLE001
            return False

    def ensure_models(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        for name, url in MODEL_URLS.items():
            p = self.dir / name
            if not p.exists() or p.stat().st_size < 10000:
                log.info("Downloading %s ...", name)
                urllib.request.urlretrieve(url, p)  # noqa: S310 - fixed https URL

    def load(self) -> bool:
        if self.face is not None:
            return True
        try:
            from mediapipe.tasks.python import BaseOptions, vision

            self.ensure_models()
            self.face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(self.dir / "face_landmarker.task")),
                num_faces=12, min_face_detection_confidence=0.4, min_face_presence_confidence=0.4,
                output_facial_transformation_matrixes=True))
            self.det = vision.ObjectDetector.create_from_options(vision.ObjectDetectorOptions(
                base_options=BaseOptions(model_asset_path=str(self.dir / "efficientdet_lite0.tflite")),
                score_threshold=0.35, max_results=10, category_allowlist=["cell phone", "book", "laptop"]))
            self.error = None
            return True
        except Exception as e:  # noqa: BLE001
            self.error = f"{type(e).__name__}: {e}"[:200]
            log.warning("MediaPipe proctoring unavailable: %s", self.error)
            self.face = self.det = None
            return False

    @staticmethod
    def head_angles(matrix) -> tuple[float, float]:
        """Yaw / pitch (degrees) of the face's forward axis from MediaPipe's facial transformation matrix."""
        m = np.asarray(matrix, dtype=float).reshape(4, 4)
        f = m[:3, 2]                                    # canonical face looks along +Z
        f = f / (np.linalg.norm(f) + 1e-9)
        yaw = math.degrees(math.atan2(f[0], f[2]))
        pitch = math.degrees(math.atan2(f[1], math.hypot(f[0], f[2])))
        return yaw, pitch

    def analyze(self, jpeg: bytes) -> Frame | None:
        if not self.load():
            return None
        import mediapipe as mp
        from PIL import Image

        img = np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))
        h, w = img.shape[:2]
        mimg = mp.Image(image_format=mp.ImageFormat.SRGB, data=img)
        people: list[Person] = []
        res = self.face.detect(mimg)
        for i, lms in enumerate(res.face_landmarks or []):
            xs = [p.x for p in lms]
            ys = [p.y for p in lms]
            box = (max(0.0, min(xs)), max(0.0, min(ys)), min(1.0, max(xs)), min(1.0, max(ys)))
            yaw = pitch = None
            if res.facial_transformation_matrixes and i < len(res.facial_transformation_matrixes):
                yaw, pitch = self.head_angles(res.facial_transformation_matrixes[i])
                pitch *= self.pitch_sign
            cx = (box[0] + box[2]) / 2
            face_w = (box[2] - box[0]) * w
            focal = (w / 2) / math.tan(math.radians(self.hfov / 2))
            dist = 0.15 * focal / face_w if face_w > 4 else None        # a face is ~15 cm wide
            people.append(Person(x=cx, yaw=yaw, pitch=pitch, box=box, distance_m=dist,
                                 bearing_deg=(0.5 - cx) * self.hfov))
        objects = []
        for d in self.det.detect(mimg).detections or []:
            c = d.categories[0]
            b = d.bounding_box
            objects.append({"label": c.category_name, "score": float(c.score),
                            "box": (b.origin_x / w, b.origin_y / h, (b.origin_x + b.width) / w, (b.origin_y + b.height) / h)})
        return attach_objects(Frame(people, "mediapipe", objects))


def attach_objects(frame: Frame) -> Frame:
    """Give each detected object to the nearest face (horizontally); keep the rest unassigned."""
    rest = []
    for o in frame.objects:
        flag = OBJECT_FLAGS.get(o["label"].lower())
        if not flag:
            continue
        ox = (o["box"][0] + o["box"][2]) / 2
        near = min(frame.people, key=lambda p: abs(p.x - ox), default=None)
        if near is not None and abs(near.x - ox) < 0.22:
            near.objects.append(o["label"].lower())
            near.score = max(near.score, o["score"])
        else:
            rest.append(o)
    frame.objects = rest
    return frame


PROCTOR_PROMPT = """You are the exam-proctoring camera of a robot in an exam hall. Look at this ONE photo.
Answer ONLY with JSON:
{"students": [{"position": <0.0 left edge .. 1.0 right edge of the image>,
               "looking_at_neighbour": <bool, head clearly turned toward another student's paper>,
               "looking_down_at_lap": <bool, head bowed toward the lap or under the desk, not at their paper>,
               "items": [<prohibited items this student has: "phone", "notes", "earpiece">]}],
 "confidence": <0..1>}
Only report what you can clearly see. Writing on the exam paper is normal. Never guess who anyone is."""


async def vlm_check(model, jpeg_b64: str) -> list[Person]:
    from langchain_core.messages import HumanMessage, SystemMessage

    resp = await model.ainvoke([SystemMessage(content=PROCTOR_PROMPT),
                                HumanMessage(content=[{"type": "text", "text": "Check this exam photo."},
                                                      {"type": "image_url",
                                                       "image_url": {"url": f"data:image/jpeg;base64,{jpeg_b64}"}}])])
    data = extract_json(message_text(resp))
    out = []
    for s in (data or {}).get("students", []) if isinstance(data, dict) else []:
        p = Person(x=float(s.get("position", 0.5)), objects=[i for i in s.get("items", []) if i in ("phone", "notes", "earpiece")],
                   score=float(data.get("confidence", 0.7)))
        if s.get("looking_at_neighbour"):
            p.yaw = 60.0
        if s.get("looking_down_at_lap"):
            p.pitch = -60.0
        out.append(p)
    return out


# ============================================================================ tracker
@dataclass
class Track:
    tid: int
    x: float
    first: float
    last: float
    yaw_since: float | None = None
    down_since: float | None = None
    obj_seen: dict = field(default_factory=dict)       # label -> count
    flagged: dict = field(default_factory=dict)        # flag -> time
    person: Person | None = None


class Tracker:
    """Follows faces while the robot watches one view, and decides when behaviour becomes a flag."""

    def __init__(self, head_turn_deg: float = 35, head_turn_s: float = 3.0, look_down_deg: float = 40,
                 look_down_s: float = 8.0, detect: dict | None = None):
        self.head_turn_deg, self.head_turn_s = head_turn_deg, head_turn_s
        self.look_down_deg, self.look_down_s = look_down_deg, look_down_s
        self.detect = {"objects": True, "head": True, "looking_down": True, **(detect or {})}
        self.tracks: list[Track] = []
        self._next = 1

    def reset(self):
        self.tracks = []

    def suspicious(self) -> bool:
        """Something is building up: keep watching this view a little longer."""
        return any(t.yaw_since is not None or t.down_since is not None or t.obj_seen for t in self.tracks)

    def update(self, frame: Frame, now: float | None = None, expected_yaw: float = 0.0) -> list[dict]:
        now = time.time() if now is None else now
        flags = []
        used = set()
        for p in frame.people:
            tr = min((t for t in self.tracks if t.tid not in used), key=lambda t: abs(t.x - p.x), default=None)
            if tr is None or abs(tr.x - p.x) > 0.09:
                tr = Track(self._next, p.x, now, now)
                self._next += 1
                self.tracks.append(tr)
            used.add(tr.tid)
            tr.x, tr.last, tr.person = p.x, now, p
            # --- head turned (fair: must exceed the limit whichever way the viewing angle is read)
            if p.yaw is not None and self.detect["head"]:
                dev = min(abs(p.yaw - expected_yaw), abs(p.yaw + expected_yaw))
                if dev > self.head_turn_deg:
                    tr.yaw_since = now if tr.yaw_since is None else tr.yaw_since
                    if now - tr.yaw_since >= self.head_turn_s:
                        flags.append(self._flag(tr, "head_turn", now, f"head turned {abs(p.yaw):.0f} degrees for "
                                                                       f"{now - tr.yaw_since:.0f} s"))
                else:
                    tr.yaw_since = None
            # --- looking down a long time
            if p.pitch is not None and self.detect["looking_down"]:
                if p.pitch < -self.look_down_deg:
                    tr.down_since = now if tr.down_since is None else tr.down_since
                    if now - tr.down_since >= self.look_down_s:
                        flags.append(self._flag(tr, "looking_down", now, f"head down {abs(p.pitch):.0f} degrees for "
                                                                          f"{now - tr.down_since:.0f} s"))
                else:
                    tr.down_since = None
            # --- prohibited objects
            if self.detect["objects"]:
                for o in set(p.objects):
                    kind = OBJECT_FLAGS.get(o, o if o in FLAGS else None)
                    if not kind:
                        continue
                    tr.obj_seen[kind] = tr.obj_seen.get(kind, 0) + 1
                    if tr.obj_seen[kind] >= 2 or p.score >= 0.8:
                        flags.append(self._flag(tr, kind, now, f"{FLAGS[kind]['title'].lower()} seen"))
        self.tracks = [t for t in self.tracks if now - t.last < 6]
        return [f for f in flags if f]

    def _flag(self, tr: Track, kind: str, now: float, detail: str) -> dict | None:
        if kind in tr.flagged and now - tr.flagged[kind] < 90:          # one flag per seat and kind per 90 s
            return None
        tr.flagged[kind] = now
        p = tr.person
        return {"type": kind, "title": FLAGS[kind]["title"], "detail": detail, "track": tr.tid, "x": p.x,
                "box": p.box, "distance_m": p.distance_m, "bearing_deg": p.bearing_deg, "ts": now}


# ============================================================================ evidence photo
def annotate(jpeg: bytes, flags: list[dict], caption: str = "") -> bytes:
    """Draw a box and label around each flagged student."""
    from PIL import Image, ImageDraw, ImageFont

    im = Image.open(io.BytesIO(jpeg)).convert("RGB")
    d = ImageDraw.Draw(im)
    W, H = im.size
    try:
        font = ImageFont.load_default(size=max(13, H // 28))
    except TypeError:                                   # Pillow < 10.1
        font = ImageFont.load_default()
    for f in flags:
        b = f.get("box") or (max(0, f["x"] - 0.08), 0.3, min(1, f["x"] + 0.08), 0.75)
        x0, y0, x1, y1 = b[0] * W, b[1] * H, b[2] * W, b[3] * H
        pad = 0.15 * (x1 - x0)
        box = (max(0, x0 - pad), max(24, y0 - pad), min(W - 1, x1 + pad), min(H - 30, y1 + pad))
        d.rectangle(box, outline=(255, 178, 36), width=3)
        label = f["title"]
        tw = d.textlength(label, font=font) + 12
        bx = min(box[0], W - tw)
        d.rectangle((bx, box[1] - 22, bx + tw, box[1]), fill=(255, 178, 36))
        d.text((bx + 6, box[1] - 20), label, fill=(13, 21, 48), font=font)
    if caption:
        d.rectangle((0, H - 26, W, H), fill=(13, 21, 48))
        d.text((8, H - 22), caption, fill=(238, 242, 255), font=font)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=85)
    return out.getvalue()


def decode(snapshot: dict) -> bytes:
    return base64.b64decode(snapshot["image_b64"])
