"""Exam monitoring (proctoring): the robot patrols the exam room, watches every student and listens.

Every few metres along the room's patrol route it looks all the way round (camera pan left / centre /
right, then the robot turns 180 degrees and does it again = 360 degrees). In each view it watches for a
few seconds, longer if something looks odd, and at the same time listens:

  * head turned past the limit for 3 s (looking at a neighbour's paper)   -> flag
  * head bowed past the limit for 8 s (looking at the lap / under the desk) -> flag
  * a phone, notes / cheat sheet or an earpiece seen                       -> flag
  * talking or whispering (voice louder than the room's quiet level)       -> finds the voice with the mic
  * a sudden noise (something dropped, a bang)                             -> photo of where it came from

On a flag the robot saves a photo with the student boxed, drives closer, takes a close photo, tells the
student to stop ("Please stop cheating ..."), notifies every signed-in app user with the photo, then
carries on patrolling. Each session is saved with all its incidents and can be printed as a report.

Privacy: the robot never identifies anyone. Students are anonymous seats; photos are only visible to
signed-in users. Privacy mode turns the camera off, and monitoring then works on sound alone.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
import uuid
from pathlib import Path

from . import proctor as P
from .agent.text import spoken_zone

log = logging.getLogger(__name__)

MARGIN_DB = {"high": 4.0, "normal": 6.0, "low": 10.0}
VIEW_PANS = (-60.0, 0.0, 60.0)          # three views per side; with a 180 degree turn = 360 degrees
DETECT_DEFAULT = {"head": True, "looking_down": True, "objects": True, "talking": True, "whisper": True, "noise": True}


def _side(rel: float) -> str:
    a = abs(rel)
    if a <= 20:
        return "in front of me"
    if a >= 160:
        return "behind me"
    side = "left" if rel > 0 else "right"
    return f"ahead on my {side}" if a < 70 else f"on my {side}" if a <= 110 else f"behind me on the {side}"


class ExamMonitor:
    def __init__(self, make_tools, notify=None, store=None):
        self.make_tools = make_tools          # (robot_id, user) -> RobotTools
        self.notify = notify                  # async (msg: dict) -> None, set by main.py (WebSocket hub)
        self.store = store
        self.task: asyncio.Task | None = None
        self.session: dict = {}
        self._mp: P.MediaPipeProctor | None = None
        self._last_ai = 0.0

    # ------------------------------------------------------------------ state
    @property
    def active(self) -> bool:
        return self.task is not None and not self.task.done()

    def status(self) -> dict:
        s = dict(self.session)
        s["active"] = self.active
        if s.get("ends_at"):
            s["minutes_left"] = max(0, round((s["ends_at"] - time.time()) / 60, 1)) if self.active else 0
        return s

    def describe(self) -> str:
        s = self.session
        if not s:
            return "I haven't monitored any exam yet. Say \"Monitor the exam in <room> for 60 minutes\" to start."
        where = spoken_zone(s.get("zone")) if s.get("zone") else "this room"
        incs = s.get("incidents", [])
        if self.active:
            left = max(0, round((s["ends_at"] - time.time()) / 60))
            head = f"I'm monitoring {where}, {left} minutes left. "
        else:
            head = f"The last monitoring session in {where} has ended. "
        if not incs:
            return head + ("Everything has been fine so far." if self.active else "Everything was fine.")
        counts: dict[str, int] = {}
        for i in incs:
            counts[i["title"].lower()] = counts.get(i["title"].lower(), 0) + 1
        parts = ", ".join(f"{n} {k}" for k, n in counts.items())
        last = incs[-1]
        when = time.strftime("%H:%M", time.localtime(last["ts"]))
        return head + f"I flagged {len(incs)} incident{'s' if len(incs) > 1 else ''}: {parts}. The last at {when}: {last['summary']}"

    async def _emit(self, robot_id: str, event: str, data: dict):
        if self.notify:
            try:
                await self.notify({"kind": "events", "robot_id": robot_id,
                                   "data": {"type": "event", "event": event, "ts": time.time(), "data": data}})
            except Exception as e:  # noqa: BLE001
                log.warning("monitor notify failed: %s", e)

    def _save(self):
        if self.store and self.session.get("id"):
            try:
                self.store.save_exam_session({k: v for k, v in self.session.items() if not k.startswith("_")})
            except Exception as e:  # noqa: BLE001
                log.warning("saving exam session failed: %s", e)

    # ------------------------------------------------------------------ control
    async def start(self, robot_id: str, zone: str | None, minutes: float, sensitivity: str = "normal",
                    user: str | None = None, mode: str = "patrol", detect: dict | None = None) -> str:
        if self.active:
            await self.stop("replaced by a new session")
        minutes = max(1.0, min(float(minutes or 60), 600.0))
        sens = sensitivity if sensitivity in MARGIN_DB else "normal"
        mode = mode if mode in ("patrol", "stay") else "patrol"
        det = {**DETECT_DEFAULT, **{k: bool(v) for k, v in (detect or {}).items() if k in DETECT_DEFAULT}}
        self.session = {"id": uuid.uuid4().hex[:10], "robot_id": robot_id, "zone": zone, "started": time.time(),
                        "ends_at": time.time() + minutes * 60, "minutes": minutes, "sensitivity": sens, "mode": mode,
                        "detect": det, "incidents": [], "phase": "starting", "level_db": None, "baseline_db": None,
                        "started_by": user, "views": 0, "rounds": 0, "vision": None, "students_seen": 0}
        self.task = asyncio.create_task(self._run(robot_id, zone, user))
        where = spoken_zone(zone) if zone else "here"
        how = "walk around the room" if mode == "patrol" else "stay in the middle of the room"
        return (f"Starting exam monitoring {'in ' + where if zone else 'here'} for {minutes:.0f} minutes. I'll {how}, look "
                "all the way round, and listen. If I see a phone, notes or an earpiece, someone looking at another "
                "paper, or I hear talking, I'll ask them to stop and send you a photo.")

    async def stop(self, reason: str = "stopped") -> str:
        if not self.active:
            return "I'm not monitoring anything right now."
        self.session["stop_reason"] = reason
        self.task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(self.task), 10)
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):  # noqa: BLE001
            pass
        n = len(self.session.get("incidents", []))
        return f"Exam monitoring stopped. {'Nothing to report.' if not n else f'I flagged {n} incident' + ('s.' if n > 1 else '.')}"

    # ------------------------------------------------------------------ vision
    def _vision_source(self, tools, snap: dict) -> str | None:
        mode = (tools.s.proctor_vision or "auto").lower()
        if mode == "off" or snap.get("privacy"):
            return None
        truth = snap.get("sim_truth") or {}
        if mode in ("auto", "sim") and "students" in truth and not truth.get("webcam"):
            return "sim"
        if mode in ("auto", "mediapipe") and P.MediaPipeProctor.available():
            if self._mp is None:
                self._mp = P.MediaPipeProctor(str(Path(tools.s.data_dir) / "models"),
                                              hfov_deg=float(self.session.get("_hfov", 62.2)))
            if self._mp.error is None or mode == "mediapipe":
                return "mediapipe"
        if mode in ("auto", "ai") and getattr(tools.vision, "model", None) is not None:
            return "ai"
        return None

    async def _analyze(self, tools, snap: dict) -> P.Frame | None:
        src = self._vision_source(tools, snap)
        self.session["vision"] = src
        if src == "sim":
            return P.from_sim(snap)
        if src == "mediapipe":
            fr = await asyncio.to_thread(self._mp.analyze, P.decode(snap))
            if fr is None:
                self.session["vision_error"] = self._mp.error
            return fr
        return None

    async def _ai_check(self, tools, snap: dict) -> P.Frame | None:
        """Ask the vision AI (Gemini / GPT-4o) about notes and earpieces, at most every 8 s."""
        model = getattr(tools.vision, "model", None)
        if model is None or not tools.s.proctor_ai_checks or time.time() - self._last_ai < 8:
            return None
        self._last_ai = time.time()
        try:
            people = await asyncio.wait_for(P.vlm_check(model, snap["image_b64"]), tools.s.vlm_timeout_s)
            return P.Frame(people, "ai")
        except Exception as e:  # noqa: BLE001
            log.info("AI proctor check failed: %s", e)
            return None

    # ------------------------------------------------------------------ one view
    async def _watch(self, tools, tracker: P.Tracker, audio: dict) -> tuple[list[dict], dict | None, list[dict]]:
        """Watch the current view. Returns (visual flags, the snapshot they were seen in, audio events)."""
        s = tools.s
        tracker.reset()
        start = time.time()
        end = start + s.proctor_dwell_s
        hard_end = start + max(s.proctor_dwell_s, s.proctor_look_down_s + 3, s.proctor_head_turn_s + 3)
        snap, seen = None, 0
        while time.time() < end:
            snap_r, a = await asyncio.gather(tools._cmd("snapshot", timeout=15), tools._cmd("listen_audio", seconds=1.0),
                                             return_exceptions=True)
            if not isinstance(a, Exception):
                ev = self._audio(a, audio)
                if ev:
                    return [], (snap_r if not isinstance(snap_r, Exception) else None), [ev]
            if isinstance(snap_r, Exception):
                await asyncio.sleep(0.5)
                continue
            snap = snap_r
            frame = await self._analyze(tools, snap)
            if frame is not None:
                seen = max(seen, len(frame.people))
                flags = tracker.update(frame)
                if flags:
                    self.session["students_seen"] = max(self.session["students_seen"], seen)
                    return flags, snap, []
                if tracker.suspicious():
                    end = min(hard_end, max(end, time.time() + 1.5))
        self.session["students_seen"] = max(self.session["students_seen"], seen)
        if snap is not None and self.session["detect"]["objects"]:
            fr = await self._ai_check(tools, snap)
            if fr is not None and fr.people:
                flags = tracker.update(fr)
                if flags:
                    return flags, snap, []
        return [], snap, []

    def _audio(self, a: dict, st: dict) -> dict | None:
        """Track the room's quiet level and decide whether a sound needs action."""
        s, det = self.session, self.session["detect"]
        db = float(a.get("db", 0))
        s["level_db"] = round(db, 1)
        label = a.get("label")
        talking = bool(a.get("voice_like")) or label in ("speech", "crowd")
        if not talking and label not in ("whisper", "sudden_noise", "alarm"):
            st["baseline"] = max(35.0, 0.9 * st["baseline"] + 0.1 * db)
            s["baseline_db"] = round(st["baseline"], 1)
        if label == "sudden_noise" and det["noise"]:
            return {"type": "noise", "db": float(a.get("peak_db") or db)}
        if talking and db >= st["baseline"] + st["margin"] and det["talking"]:
            st["talk"] += 1
            if st["talk"] >= 2:
                st["talk"] = 0
                return {"type": "talking", "db": db}
        else:
            st["talk"] = 0
        if label == "whisper" and det["whisper"]:
            st["whisper"] += 1
            if st["whisper"] >= (1 if s["sensitivity"] == "high" else 2):
                st["whisper"] = 0
                return {"type": "whisper", "db": db}
        elif not talking:
            st["whisper"] = 0
        return None

    # ------------------------------------------------------------------ responses
    def _save_image(self, tools, data: bytes) -> str:
        name = f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
        Path(tools.s.data_dir, "images", name).write_bytes(data)
        return name

    def _recent(self, kind: str, spot: tuple | None, within: float = 75.0) -> bool:
        for i in reversed(self.session["incidents"]):
            if time.time() - i["ts"] > within:
                break
            if i["type"] == kind and (spot is None or i.get("spot") is None or
                                      math.dist(spot, i["spot"]) < 0.8):
                return True
        return False

    async def _record(self, robot_id: str, user: str | None, inc: dict):
        self.session["incidents"].append(inc)
        if self.store:
            self.store.audit(f"monitor:{user}", "exam_incident", {k: inc.get(k) for k in ("type", "title", "summary", "image")})
        self._save()
        await self._emit(robot_id, "proctor_flag", {"zone": self.session.get("zone"), **inc,
                                                    "count": len(self.session["incidents"])})

    async def _handle_visual(self, tools, robot_id, user, flags: list[dict], snap: dict, back_to: tuple | None):
        s = self.session
        pose = snap.get("pose") or {}
        pan = float((snap.get("pan_tilt") or {}).get("pan", 0))
        f = flags[0]
        rel = pan + float(f.get("bearing_deg") or 0)            # student direction relative to the robot
        spot = None
        if f.get("distance_m") and "x" in pose:
            a = math.radians(float(pose.get("heading_deg", 0)) + rel)
            spot = (pose["x"] + f["distance_m"] * math.cos(a), pose["y"] + f["distance_m"] * math.sin(a))
        flags = [g for g in flags if not self._recent(g["type"], spot)]
        if not flags:
            return
        f = flags[0]
        titles = " and ".join(dict.fromkeys(g["title"].lower() for g in flags))
        dist = f" about {f['distance_m']:.1f} m away" if f.get("distance_m") else ""
        where = f"{_side(rel)}{dist}"
        s["phase"] = "responding"
        image = self._save_image(tools, P.annotate(P.decode(snap), flags,
                                                   f"{time.strftime('%H:%M:%S')}  {titles}  ({where})"))
        close = None
        moved = 0.0
        if tools.s.proctor_approach:
            try:
                if abs(rel) > 8:
                    await tools._cmd("turn", angle_deg=rel)
                await tools._cmd("pan_tilt", pan=0, tilt=0)
                step = min(2.0, (f.get("distance_m") or 0) - 0.9)
                if step > 0.25:
                    ack = await tools.bridge.send(robot_id, "move", {"distance_m": step}, timeout=60, issued_by=tools.user)
                    moved = float((ack.result or {}).get("traveled_m") or 0)
                near = await tools._cmd("snapshot", timeout=15)
                fr = await self._analyze(tools, near)
                boxes = []
                if fr is not None and fr.people:
                    p = min(fr.people, key=lambda q: abs(q.x - 0.5))
                    boxes = [{**g, "x": p.x, "box": p.box} for g in flags]
                close = self._save_image(tools, P.annotate(P.decode(near), boxes or [{**flags[0], "x": 0.5, "box": None}],
                                                           f"{time.strftime('%H:%M:%S')}  close-up"))
            except Exception as e:  # noqa: BLE001
                log.warning("approach failed: %s", e)
        say = P.FLAGS[f["type"]]["say"]
        warned = False
        try:
            r = await tools._cmd("speak", text=f"Excuse me. {say}")
            warned = bool((r or {}).get("spoken", True))       # False = this robot has no speaker
        except Exception as e:  # noqa: BLE001
            log.warning("speak failed: %s", e)
        detail = "; ".join(dict.fromkeys(g["detail"] for g in flags))
        summary = (f"{titles.capitalize()}: a student {where} ({detail}). "
                   + ("I went closer, " if moved >= 0.2 else "")
                   + ("asked them to stop and took a photo." if warned else "took a photo for you to check."))
        await self._record(robot_id, user, {"ts": time.time(), "type": f["type"], "title": f["title"],
                                            "types": [g["type"] for g in flags], "summary": summary, "detail": detail,
                                            "image": image, "close_image": close, "warned": warned, "where": where,
                                            "spot": spot, "waypoint": s.get("waypoint")})
        if back_to:
            s["phase"] = "returning"
            await tools._cmd("go_to_point", x=back_to[0], y=back_to[1], timeout=120)

    async def _handle_audio(self, tools, robot_id, user, ev: dict, snap: dict | None, audio: dict, back_to: tuple | None):
        s = self.session
        s["phase"] = "responding"
        tools.images = []
        if ev["type"] == "noise":
            if self._recent("noise", None, 20):
                return
            image = None
            if snap is not None:
                image = self._save_image(tools, P.annotate(P.decode(snap), [], f"{time.strftime('%H:%M:%S')}  sudden noise"))
            pan = float(((snap or {}).get("pan_tilt") or {}).get("pan", 0))
            where = _side(pan)
            spot = f" at patrol point {s['waypoint']}" if s.get("waypoint") else ""
            summary = (f"Sudden noise ({ev['db']:.0f} dB peak){spot}, like something dropped or banged. "
                       f"I took a photo of the view {where} at that moment.")
            await self._record(robot_id, user, {"ts": time.time(), "type": "noise", "title": P.FLAGS["noise"]["title"],
                                                "types": ["noise"], "summary": summary, "image": image, "close_image": None,
                                                "warned": False, "where": where, "db": ev["db"], "waypoint": s.get("waypoint")})
            return
        say = P.FLAGS[ev["type"]]["say"]
        min_db = audio["baseline"] + audio["margin"] - 2 if ev["type"] == "talking" else 0.0
        res = await tools.find_sound(warn=True, message=f"Excuse me. {say}", min_db=min_db)
        d = res["data"]
        if d.get("talking") or ev["type"] == "whisper":
            image = d.get("image_file")
            if image is None and snap is not None:
                image = self._save_image(tools, P.decode(snap))
            summary = res["summary"] if d.get("talking") else (
                f"Whispering heard ({ev['db']:.0f} dB) but it stopped before I could find it. Photo of the area taken.")
            await self._record(robot_id, user, {"ts": time.time(), "type": ev["type"], "title": P.FLAGS[ev["type"]]["title"],
                                                "types": [ev["type"]], "summary": summary, "image": image,
                                                "close_image": None, "warned": bool(d.get("warned")),
                                                "where": d.get("direction"), "db": d.get("db") or ev["db"],
                                                "waypoint": s.get("waypoint")})
        if back_to:
            s["phase"] = "returning"
            await tools._cmd("go_to_point", x=back_to[0], y=back_to[1], timeout=120)

    # ------------------------------------------------------------------ main loop
    def _route(self, tools, zone: str | None) -> list[tuple[float, float]]:
        r = tools.bridge.robots.get(tools.robot_id)
        info = (r.info if r else None) or {}
        self.session["_hfov"] = float((info.get("camera") or {}).get("hfov_deg", 62.2))
        z = (info.get("zones") or {}).get(zone or "") or {}
        route = (info.get("patrols") or {}).get(zone or "") or []
        if self.session["mode"] == "stay" or not route:
            return [(float(z["x"]), float(z["y"]))] if "x" in z else []
        return [(float(p[0]), float(p[1])) for p in route]

    async def _run(self, robot_id: str, zone: str | None, user: str | None):
        s = self.session
        tools = self.make_tools(robot_id, f"monitor:{user or 'operator'}")
        st = tools.s
        tracker = P.Tracker(st.proctor_head_turn_deg, st.proctor_head_turn_s, st.proctor_look_down_deg,
                            st.proctor_look_down_s, {k: s["detect"][k] for k in ("head", "looking_down", "objects")})
        try:
            if zone and tools.current_zone() != zone:
                s["phase"] = "driving"
                await tools._cmd("go_to_zone", zone=zone, timeout=st.navigation_timeout_s)
            try:
                await tools._cmd("speak", text="This exam is now monitored. Phones, notes and earpieces are not allowed. "
                                               "Please keep your eyes on your own paper and stay silent.")
            except Exception:  # noqa: BLE001
                pass
            s["phase"] = "calibrating"
            quiet: list[float] = []
            for _ in range(3):
                a = await tools._cmd("listen_audio", seconds=1.5)
                if not tools._talking(a) and a.get("label") not in ("whisper", "sudden_noise"):
                    quiet.append(float(a.get("db", 40)))
            audio = {"baseline": max(35.0, min(quiet)) if quiet else 40.0, "margin": MARGIN_DB[s["sensitivity"]],
                     "talk": 0, "whisper": 0}
            s["baseline_db"] = round(audio["baseline"], 1)
            route = self._route(tools, zone)
            s["route"] = route
            s["ends_at"] = time.time() + s["minutes"] * 60     # the clock starts once the robot is in place
            self._save()
            await self._emit(robot_id, "monitoring_started", {"zone": zone, "minutes": s["minutes"], "mode": s["mode"]})
            forward = True
            blocked = 0
            while time.time() < s["ends_at"]:
                order = list(range(len(route))) or [None]
                if not forward:
                    order.reverse()
                for wi in order:
                    if time.time() >= s["ends_at"]:
                        break
                    point = route[wi] if wi is not None else None
                    s["waypoint"] = (wi + 1) if wi is not None else None
                    if point and len(route) > 1:
                        s["phase"] = "patrolling"
                        try:
                            await tools._cmd("go_to_point", x=point[0], y=point[1], timeout=120)
                            blocked = 0
                        except Exception as e:  # noqa: BLE001 - a student or bag in the aisle must not end the exam watch
                            if any(w in str(e).lower() for w in ("emergency", "estop", "e-stop", "safe hold", "safe_hold")):
                                raise
                            blocked += 1
                            log.warning("patrol: could not reach %s (%s) - watching from here instead", point, e)
                            if blocked >= 3:          # aisle keeps being blocked: stay put and watch from here
                                route = []
                                s["route"] = route
                                s["mode_note"] = "aisle blocked - watching from one place"
                                break
                    for half in (0, 1):
                        if half:
                            await tools._cmd("turn", angle_deg=180)
                        for pan in VIEW_PANS:
                            if time.time() >= s["ends_at"]:
                                break
                            s["phase"] = "watching"
                            s["view_pan"] = pan
                            s["view_dir"] = (pan + 180 * half + 180) % 360 - 180   # where the camera looks, 360 deg
                            await tools._cmd("pan_tilt", pan=pan, tilt=0)
                            flags, snap, events = await self._watch(tools, tracker, audio)
                            s["views"] += 1
                            if flags and snap is not None:
                                await self._handle_visual(tools, robot_id, user, flags, snap, point)
                            for ev in events:
                                await self._handle_audio(tools, robot_id, user, ev, snap, audio, point)
                    await tools._cmd("pan_tilt", pan=0, tilt=0)
                forward = not forward
                s["rounds"] += 1
                self._save()
            s["stop_reason"] = s.get("stop_reason") or "time is up"
        except asyncio.CancelledError:
            try:
                await tools._cmd("stop", timeout=5)
            except Exception:  # noqa: BLE001
                pass
            raise
        except Exception as e:  # noqa: BLE001
            log.exception("exam monitoring failed")
            s["stop_reason"] = f"error: {e}"
            await self._emit(robot_id, "monitoring_error", {"zone": zone, "error": str(e)})
        finally:
            s["phase"] = "finished"
            s["ended"] = time.time()
            n = len(s.get("incidents", []))
            self._save()
            try:
                await tools._cmd("pan_tilt", pan=0, tilt=0)
                await tools._cmd("speak", text="Exam monitoring has finished.")
            except Exception:  # noqa: BLE001
                pass
            await self._emit(robot_id, "monitoring_finished", {"zone": zone, "incidents": n, "session": s.get("id"),
                                                               "reason": s.get("stop_reason")})
            if self.store:
                self.store.audit(f"monitor:{user}", "monitoring_finished",
                                 {"zone": zone, "incidents": n, "reason": s.get("stop_reason"), "session": s.get("id")})
