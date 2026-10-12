"""Agent tools - each one turns into MQTT commands to the robot (or a memory query).

These are the tools the LangGraph InspectionAgent can call. Every call has a timeout
(handled by the bridge) and raises ToolError on failure so the graph can retry or
fall back.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from ..config import Settings
from ..memory import SemanticMemory
from ..mqtt_bridge import RobotBridge
from ..report import fuse
from .text import spoken_zone
from ..schemas import ZoneInspection
from ..vlm import VisionAnalyzer, decode_image

log = logging.getLogger(__name__)

# Tool catalogue shown to the LLM planner (name -> description, args)
TOOL_SPECS: dict[str, dict[str, Any]] = {
    "inspect_zone": {"desc": "Drive to a named zone and run the FULL audit there: camera snapshot analysed by the "
                             "vision-language model (occupancy, lights, projector, exits, extinguisher, hazards), "
                             "temperature/humidity/air-quality reading and acoustic equipment check. Use this for "
                             "any request to inspect/check/audit a room.",
                     "args": {"zone": "string, one of the known zones"}},
    "go_to_zone": {"desc": "Drive to a named zone without inspecting.", "args": {"zone": "string"}},
    "return_home": {"desc": "Drive back to the Home position.", "args": {}},
    "move": {"desc": "Drive straight. Negative distance = reverse. Stops safely by itself at an obstacle.",
             "args": {"distance_m": "number (metres)"}},
    "turn": {"desc": "Turn in place. Positive = left/counter-clockwise.", "args": {"angle_deg": "number (degrees)"}},
    "stop": {"desc": "Stop all motion immediately.", "args": {}},
    "pan_tilt": {"desc": "Point the camera.", "args": {"pan": "number -90..90", "tilt": "number -45..60"}},
    "capture_and_analyze": {"desc": "Take a photo where the robot is now and analyse it with the vision model. Use for "
                                   "'what do you see', 'what is that', 'take a picture', 'is anyone here'. The reply "
                                   "is a first-person answer ('I see ...').",
                            "args": {"focus": "string, optional - the operator's question about the picture"}},
    "read_environment": {"desc": "Read temperature, humidity, air quality / gas level at the current position.",
                         "args": {}},
    "listen_audio": {"desc": "Classify the sound at the current position (quiet room / AC or fan / crowd / alarm).",
                     "args": {}},
    "search_history": {"desc": "Semantic search over past inspection records (use for questions about the past, "
                                "trends, 'last month', 'how often', 'show me all rooms where ...').",
                       "args": {"query": "string", "zone": "string, optional", "days": "integer, optional"}},
    "get_status": {"desc": "Current robot status: position, battery, state, live sensor values.", "args": {}},
    "speak": {"desc": "Say a short message through the robot speaker.", "args": {"text": "string"}},
    "find_sound": {"desc": "Find who is talking / where a noise comes from: listen, turn to the loudest direction "
                           "(directional microphone), drive closer, take a photo. warn=true also asks them through "
                           "the speaker to stop talking.",
                   "args": {"warn": "boolean", "message": "string, optional - what to say instead of the default"}},
    "start_monitoring": {"desc": "Exam proctoring: go to the zone, patrol it (or stay in the middle), look all the "
                                 "way round with the camera and listen. Flags phones, notes / cheat sheets, earpieces, "
                                 "heads turned to a neighbour's paper, looking down too long, talking, whispering and "
                                 "sudden noises; drives to the student, tells them to stop and sends the operator a "
                                 "photo. Runs in the background until the time is up or stop_monitoring.",
                         "args": {"zone": "string, optional", "minutes": "number, default 60",
                                  "sensitivity": "low | normal | high", "mode": "patrol (default) | stay",
                                  "detect": "optional object to switch checks off, e.g. {\"noise\": false}; keys "
                                            "head, looking_down, objects, talking, whisper, noise"}},
    "stop_monitoring": {"desc": "End the current exam monitoring session.", "args": {}},
    "monitor_status": {"desc": "How the current / last monitoring session is going (incidents so far).", "args": {}},
    "check_ac": {"desc": "Focused air-conditioner check (optionally drive to a zone first): listens for the AC "
                         "compressor/fan, reads temperature + humidity, looks at the unit with the camera and "
                         "says whether the AC is running, over-cooling, not cooling or could be switched off.",
                 "args": {"zone": "string, optional"}},
    "last_findings": {"desc": "Summarise the most recent inspection results (optionally for one zone). Use for "
                              "'what did you find', 'results', 'summary'.",
                      "args": {"zone": "string, optional"}},
}


class ToolError(Exception):
    pass


NO_VISION = ("I took a photo, but no vision AI is set up on the server, so I can't judge what is in it. "
             "Add a Gemini or OpenAI key (or Ollama) in backend/.env to turn on vision.")


def usable(va):
    """Vision results we can trust for findings. A placeholder (no model, real camera) is not one."""
    if va is None:
        return None
    if va.provider in ("mock", "rule-based") and va.confidence < 0.5:
        return None
    return va


class RobotTools:
    def __init__(self, settings: Settings, bridge: RobotBridge, memory: SemanticMemory | None,
                 vision: VisionAnalyzer, robot_id: str, user: str | None = None, progress=None, store=None):
        self.s, self.bridge, self.memory, self.vision, self.store = settings, bridge, memory, vision, store
        self.robot_id, self.user = robot_id, user
        self.progress = progress or (lambda *_: asyncio.sleep(0))
        self.inspections: list[ZoneInspection] = []
        self.images: list[str] = []          # photos to show in the chat reply
        self.last_zone: str | None = None    # last zone acted on ("go there")
        self.linked_report: str | None = None

    # ------------------------------------------------------------------ helpers
    async def _cmd(self, action: str, timeout: float | None = None, **params) -> dict:
        ack = await self.bridge.send(self.robot_id, action, params, timeout=timeout, issued_by=self.user)
        if ack.status != "ok":
            raise ToolError(f"{action} failed: {ack.status} - {ack.error or ''}".strip(" -"))
        return ack.result

    def zones(self) -> list[str]:
        r = self.bridge.robots.get(self.robot_id)
        return list(((r.info or {}).get("zones") or {}).keys()) if r else []

    def _check_zone(self, zone: str) -> str:
        known = self.zones()
        if known and zone not in known:
            norm = {z.lower().replace("_", "").replace(" ", ""): z for z in known}
            key = zone.lower().replace("_", "").replace(" ", "")
            if key in norm:
                return norm[key]
            raise ToolError(f"unknown zone '{zone}'. Known zones: {', '.join(known)}")
        return zone

    def current_zone(self) -> str | None:
        r = self.bridge.robots.get(self.robot_id)
        return ((r.telemetry or {}).get("pose") or {}).get("zone") if r else None

    # ------------------------------------------------------------------ tools
    async def go_to_zone(self, zone: str) -> dict:
        zone = self._check_zone(zone)
        self.last_zone = zone
        if self.current_zone() == zone:
            return {"summary": f"Already at {spoken_zone(zone)}.", "data": {"zone": zone}}
        await self.progress({"tool": "go_to_zone", "status": "running", "summary": f"Driving to {spoken_zone(zone)}..."})
        r = await self._cmd("go_to_zone", zone=zone)
        note = f" (drove around {r['avoidance_attempts']} obstacle{'s' if r['avoidance_attempts'] > 1 else ''})" \
            if r.get("avoidance_attempts") else ""
        return {"summary": f"Arrived at {spoken_zone(zone)}{note}.", "data": r}

    async def return_home(self) -> dict:
        home = "Home" if "Home" in self.zones() or not self.zones() else self.zones()[0]
        return await self.go_to_zone(home)

    async def move(self, distance_m: float) -> dict:
        dist = float(distance_m)
        way = "forward" if dist >= 0 else "back"
        timeout = max(self.s.navigation_timeout_s, abs(dist) / 0.15 + 30)    # long corridors take a while
        if abs(dist) >= 3:
            await self.progress({"tool": "move", "status": "running", "summary": f"Driving {way} {abs(dist):.0f} m..."})
        ack = await self.bridge.send(self.robot_id, "move", {"distance_m": dist}, timeout=timeout, issued_by=self.user)
        r = ack.result or {}
        d = float(r.get("traveled_m") or 0)
        done = f"{d * 100:.0f} cm" if d < 1 else f"{d:.1f} m"
        if ack.status == "ok":
            return {"summary": f"Moved {way} {done}.", "data": r}
        if ack.status == "blocked":
            front = ((self.bridge.robots.get(self.robot_id).telemetry or {}).get("ultrasonic_cm") or {}).get("center") \
                if self.bridge.robots.get(self.robot_id) else None
            near = f" about {front:.0f} cm ahead" if isinstance(front, (int, float)) and front < 400 else ""
            return {"summary": f"I stopped after {done} because something is in the way{near}.",
                    "data": {**r, "blocked": True}}
        raise ToolError(f"move {ack.status} after {done}: {ack.error or ''}".strip(": "))

    async def turn(self, angle_deg: float) -> dict:
        r = await self._cmd("turn", angle_deg=float(angle_deg))
        a = float(angle_deg)
        what = "Turned around" if abs(abs(a) - 180) < 1 else f"Turned {'left' if a > 0 else 'right'} {abs(a):.0f}°"
        return {"summary": f"{what}.", "data": r}

    async def stop(self) -> dict:
        await self._cmd("stop", timeout=5)
        return {"summary": "Robot stopped.", "data": {}}

    async def pan_tilt(self, pan: float = 0, tilt: float = 0) -> dict:
        r = await self._cmd("pan_tilt", pan=float(pan), tilt=float(tilt))
        where = []
        if float(pan) > 5:
            where.append("left")
        elif float(pan) < -5:
            where.append("right")
        if float(tilt) > 20:
            where.append("up")
        elif float(tilt) < -5:
            where.append("down")
        return {"summary": f"Camera now looking {' and '.join(where) or 'straight ahead'}.", "data": r}

    async def speak(self, text: str) -> dict:
        await self._cmd("speak", text=text)
        return {"summary": f"Said: \"{text}\"", "data": {}}

    async def get_status(self) -> dict:
        r = self.bridge.robots.get(self.robot_id)
        t = (r.telemetry if r else None) or {}
        if not t:
            raise ToolError("no telemetry received from the robot yet")
        e = t.get("environment") or {}
        pose = t.get("pose") or {}
        b = t.get("battery") or {}
        state = {"IDLE": "ready", "MANUAL": "in manual drive", "AUTONOMOUS_PATROL": "on a mission",
                 "EMERGENCY_STOP": "emergency-stopped", "SAFE_HOLD": "in safe hold"}.get(t.get("state"), t.get("state"))
        pct = b.get("percent")
        s = f"I'm {state} at {spoken_zone(pose.get('zone'))}" + (f", battery {pct:.0f}%." if pct is not None else ".")
        if e:
            s += f" It's {e.get('temperature_c'):.1f}°C, {e.get('humidity_pct'):.0f}% humidity, air quality {e.get('aqi_label') or e.get('aqi')}."
        return {"summary": s, "data": t}

    async def _snapshot_and_analyze(self, focus: str | None = None):
        snap = await self._cmd("snapshot", timeout=15)
        image_file = f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
        Path(self.s.data_dir, "images", image_file).write_bytes(decode_image(snap["image_b64"]))
        va = await self.vision.analyze(snap, focus)
        return va, image_file, snap

    def _part_fault(self, part: str) -> str | None:
        r = self.bridge.robots.get(self.robot_id)
        h = (((r.telemetry if r else None) or {}).get("health") or {}).get(part)
        return h.get("detail") if h and not h.get("ok") else None

    async def capture_and_analyze(self, focus: str | None = None) -> dict:
        cam = self._part_fault("camera")
        if cam:
            return {"summary": f"I can't see anything: my camera is not working ({cam}). Robot health shows how to fix it.",
                    "data": {"camera_fault": cam}}
        va, image_file, snap = await self._snapshot_and_analyze(focus)
        self.images.append(image_file)
        f = (focus or "").lower()
        if usable(va) is None:
            summary = NO_VISION
        elif f.startswith("describe") or any(w in f for w in ("what do you see", "what is", "what's", "identify",
                                                              "in front", "picture", "photo", "look")):
            summary = va.answer or va.description
            if not summary.lower().startswith("i see"):
                summary = "I see this: " + summary[0].lower() + summary[1:] if summary else "I can't make out anything clearly."
        elif "talk" in f:
            n = va.occupants
            summary = (f"I see {n} {'person' if n == 1 else 'people'} here." if n else "I don't see anyone in this direction.")
        elif "people" in f:
            n = va.occupants
            summary = f"{'Nobody is' if n == 0 else 'One person is' if n == 1 else f'{n} people are'} in " \
                      f"{spoken_zone(snap.get('zone'))}."
            if n == 0 and (va.lights_on or va.projector_on):
                summary += " The room is empty but " + ("the lights are" if va.lights_on else "the projector is") + " on."
        elif "light" in f:
            on = [x for x, v in (("lights", va.lights_on), ("projector", va.projector_on), ("screens", va.monitors_on)) if v]
            summary = (f"In {spoken_zone(snap.get('zone'))} the {', '.join(on)} {'is' if len(on) == 1 else 'are'} on"
                       if on else f"Everything is switched off in {spoken_zone(snap.get('zone'))}")
            summary += f", and {'nobody is' if va.occupants == 0 else f'{va.occupants} people are'} in the room."
        else:
            summary = va.description
        return {"summary": summary, "data": {"vision": va.model_dump(), "image_file": image_file,
                                             "zone": snap.get("zone")}}

    async def read_environment(self) -> dict:
        e = await self._cmd("read_environment", timeout=60)
        comfort = {"COMFORTABLE": "comfortable", "OVERCOOLED_ENERGY_WASTE": "over-cooled",
                   "UNCOMFORTABLE_HOT_HUMID": "hot and humid", "UNCOMFORTABLE_HOT": "too warm",
                   "UNCOMFORTABLE_COLD": "too cold", "UNCOMFORTABLE_HUMID": "too humid",
                   "UNCOMFORTABLE_DRY": "too dry"}.get(str(e.get("comfort_verdict")), str(e.get("comfort_verdict") or "").lower().replace("_", " "))
        where = spoken_zone(e.get("zone")) if e.get("zone") else "here"
        s = (f"In {where} it's {e.get('temperature_c'):.1f}°C and {e.get('humidity_pct'):.0f}% humidity, "
             f"which is {comfort or 'unknown'}. Air quality is {str(e.get('aqi_label') or '').lower() or 'unknown'}"
             f" (AQI {e.get('aqi'):.0f})." if e.get("aqi") is not None else "")
        if e.get("gas_verdict") in ("WARNING", "HAZARD"):
            s += " Please ventilate the room."
        return {"summary": s.strip() or "Environment read.", "data": e}

    async def listen_audio(self) -> dict:
        a = await self._cmd("listen_audio", seconds=1.0)
        return {"summary": f"I hear {str(a.get('title') or a.get('label')).lower()} at about {a.get('db'):.0f} dB.",
                "data": a}

    async def inspect_zone(self, zone: str) -> dict:
        zone = self._check_zone(zone)
        if self.current_zone() != zone:
            await self.progress({"tool": "inspect_zone", "status": "running", "summary": f"Driving to {zone}..."})
            await self._cmd("go_to_zone", zone=zone)
        await self.progress({"tool": "inspect_zone", "status": "running", "summary": f"Sensing in {zone}..."})
        await self._cmd("pan_tilt", pan=0, tilt=10)
        results = await asyncio.gather(
            self._snapshot_and_analyze("full room audit"),
            self._cmd("read_environment", timeout=60),
            self._cmd("listen_audio", seconds=1.5),
            return_exceptions=True,
        )
        vis_r, env_r, aud_r = results
        if isinstance(vis_r, Exception) and isinstance(env_r, Exception):
            raise ToolError(f"inspection of {zone} failed: {vis_r}; {env_r}")
        va, image_file = (None, None) if isinstance(vis_r, Exception) else vis_r[:2]
        env = None if isinstance(env_r, Exception) else env_r
        audio = None if isinstance(aud_r, Exception) else aud_r
        self.last_zone = zone
        z = fuse(zone, usable(va), env, audio, image_file)
        self.inspections.append(z)
        n = len(z.anomalies)
        return {"summary": f"{zone}: " + ("fully compliant." if z.compliant else f"{n} issue(s) - "
                                          + "; ".join(a.description for a in z.anomalies[:4])),
                "data": z.model_dump()}

    async def check_ac(self, zone: str | None = None) -> dict:
        if zone:
            zone = self._check_zone(zone)
            self.last_zone = zone
            if self.current_zone() != zone:
                await self.progress({"tool": "check_ac", "status": "running", "summary": f"Driving to {spoken_zone(zone)}..."})
                await self._cmd("go_to_zone", zone=zone)
        where = spoken_zone(zone or self.current_zone())
        await self.progress({"tool": "check_ac", "status": "running", "summary": f"Checking the air-conditioning in {where}..."})
        await self._cmd("pan_tilt", pan=0, tilt=25)      # wall-mounted units sit high
        vis_r, env_r, aud_r = await asyncio.gather(
            self._snapshot_and_analyze("air-conditioning unit: is it running, display / set-point, airflow, leaks"),
            self._cmd("read_environment", timeout=60),
            self._cmd("listen_audio", seconds=2.0),
            return_exceptions=True)
        va, image_file = (None, None) if isinstance(vis_r, Exception) else vis_r[:2]
        va = usable(va)
        env = None if isinstance(env_r, Exception) else env_r
        audio = None if isinstance(aud_r, Exception) else aud_r
        if env is None and audio is None:
            raise ToolError(f"could not check the AC in {where}: {env_r}; {aud_r}")
        if image_file:
            self.images.append(image_file)
        running = bool(audio and audio.get("label") == "ac_fan")
        temp = env.get("temperature_c") if env else None
        rh = env.get("humidity_pct") if env else None
        people = va.occupants if va else None
        lo, hi = self.s.comfort_temp_min, self.s.comfort_temp_max
        level, advice = "ok", ""
        t_txt = f"{temp:.1f}°C" if temp is not None else "unknown temperature"
        if running:
            head = f"The air-conditioner in {where} is running"
            if temp is not None and temp < lo - 2:
                level = "warn"
                head += f" and the room is over-cooled at {t_txt}"
                advice = "Raise the set-point to about 24°C" + (", or switch it off since the room is empty."
                                                                 if people == 0 else ".")
            elif temp is not None and temp > hi:
                level = "alert"
                head += f" but it isn't cooling well: the room is still {t_txt}"
                advice = "Check the filter and set-point, and log a maintenance request if it stays warm."
            else:
                head += f" and the room is comfortable at {t_txt}"
                if people == 0:
                    level = "warn"
                    advice = "Nobody is in the room, so it could be switched off to save energy."
        else:
            head = f"I don't hear the air-conditioner in {where}, so it looks switched off"
            if temp is not None and temp > hi:
                level = "warn" if people == 0 else "alert"
                head += f", and the room is warm at {t_txt}"
                advice = ("Switch it on before the next session." if people == 0
                          else "People are in the room - please switch the AC on or check it is working.")
            else:
                head += f". The room is {t_txt}, which is fine"
        if rh is not None and rh > self.s.comfort_rh_max:
            advice = (advice + " " if advice else "") + f"Humidity is high at {rh:.0f}%."
        if va and getattr(va, "water_leak_or_stain", False):
            level = "alert"
            advice = (advice + " " if advice else "") + "I can also see water or a stain - check the unit for leaks."
        summary = head + "." + (" " + advice if advice else "")
        return {"summary": summary, "data": {"zone": zone, "ac_running": running, "temperature_c": temp,
                                             "humidity_pct": rh, "occupants": people, "level": level,
                                             "image_file": image_file, "audio": audio}}

    # ------------------------------------------------------------------ sound / exam monitoring
    @staticmethod
    def _talking(a: dict | None, min_db: float = 0.0) -> bool:
        return bool(a) and (a.get("voice_like") or a.get("label") in ("speech", "crowd")) and a.get("db", 0) >= min_db

    async def find_sound(self, warn: bool = False, message: str | None = None, min_db: float = 0.0,
                         max_approach_m: float = 2.1) -> dict:
        await self.progress({"tool": "find_sound", "status": "running", "summary": "Listening..."})
        a = await self._cmd("listen_audio", seconds=1.5)
        if not self._talking(a, min_db):
            return {"summary": f"It's quiet here ({a.get('db', 0):.0f} dB). I don't hear anyone talking.",
                    "data": {"talking": False, "audio": a}}
        await self.progress({"tool": "find_sound", "status": "running", "summary": "Turning to find where the voice comes from..."})
        start_heading = (((self.bridge.robots.get(self.robot_id).telemetry or {}).get("pose") or {}).get("heading_deg")
                         if self.bridge.robots.get(self.robot_id) else None)
        scan = await self._cmd("sound_scan", timeout=120, step_deg=45, seconds=0.8)
        direction = None
        moved, loudest = 0.0, float(scan.get("best_db") or a.get("db") or 0)
        if scan.get("directional_mic") and float(scan.get("spread_db") or 0) >= 3:
            if start_heading is not None:
                rel = ((float(scan["best_heading_deg"]) - float(start_heading) + 180) % 360) - 180
                direction = ("ahead" if abs(rel) <= 30 else "behind me" if abs(rel) >= 150 else
                             ("ahead on the left" if rel > 0 else "ahead on the right") if abs(rel) < 90 else
                             ("on my left" if rel > 0 else "on my right") if abs(rel) <= 100 else
                             ("behind me on the left" if rel > 0 else "behind me on the right"))
            await self.progress({"tool": "find_sound", "status": "running", "summary": "Driving toward the voice..."})
            while moved < max_approach_m - 0.05:
                step = min(0.7, max_approach_m - moved)
                ack = await self.bridge.send(self.robot_id, "move", {"distance_m": step}, timeout=60, issued_by=self.user)
                moved += float((ack.result or {}).get("traveled_m") or 0)
                if ack.status != "ok":
                    break                       # reached a desk / person / wall: close enough
                b = await self._cmd("listen_audio", seconds=1.0)
                if not self._talking(b) or float(b.get("db", 0)) < loudest - 1.5:
                    break                       # quieter: we passed them or they stopped
                loudest = max(loudest, float(b.get("db", 0)))
        snap_summary, image = "", None
        try:
            va, image, _snap = await self._snapshot_and_analyze("people talking: how many people and what they are doing")
            self.images.append(image)
            if usable(va) is not None and va.occupants:
                snap_summary = f" I can see {va.occupants} {'person' if va.occupants == 1 else 'people'} there."
        except Exception as e:  # noqa: BLE001
            log.warning("photo during find_sound failed: %s", e)
        said = ""
        if warn:
            text = message or "Excuse me. Please stop talking. This is an exam."
            try:
                await self._cmd("speak", text=text)
                said = " I asked them to stop talking."
            except Exception as e:  # noqa: BLE001
                log.warning("speak failed: %s", e)
        where = f"Someone is talking {direction}" if direction else "Someone is talking nearby"
        how = f", I moved {moved:.1f} m toward them" if moved >= 0.2 else ""
        if not direction:
            how = " (I couldn't tell the exact direction)" if not scan.get("directional_mic") or float(scan.get("spread_db") or 0) < 3 else ""
        summary = f"{where}{how} ({loudest:.0f} dB).{snap_summary}{said}"
        return {"summary": summary, "data": {"talking": True, "db": loudest, "direction": direction, "moved_m": moved,
                                             "image_file": image, "warned": bool(said), "scan": scan}}

    async def start_monitoring(self, zone: str | None = None, minutes: float = 60, sensitivity: str = "normal",
                               mode: str = "patrol", detect: dict | None = None) -> dict:
        mon = getattr(self, "monitor", None)
        if mon is None:
            raise ToolError("monitoring is not available")
        if zone:
            zone = self._check_zone(zone)
            self.last_zone = zone
        msg = await mon.start(self.robot_id, zone or self.current_zone(), float(minutes or 60), sensitivity, self.user,
                              mode=mode, detect=detect if isinstance(detect, dict) else None)
        return {"summary": msg, "data": mon.status()}

    async def stop_monitoring(self) -> dict:
        mon = getattr(self, "monitor", None)
        if mon is None or not mon.active:
            return {"summary": "I'm not monitoring anything right now.", "data": {}}
        msg = await mon.stop("stopped by " + (self.user or "operator"))
        return {"summary": msg, "data": mon.status()}

    async def monitor_status(self) -> dict:
        mon = getattr(self, "monitor", None)
        if mon is None:
            raise ToolError("monitoring is not available")
        return {"summary": mon.describe(), "data": mon.status()}

    async def last_findings(self, zone: str | None = None) -> dict:
        if self.store is None:
            raise ToolError("report store not available")
        if zone:
            zone = self._check_zone(zone)
        reps = self.store.list_reports(limit=20, zone=zone)
        if not reps:
            return {"summary": "I haven't inspected " + (spoken_zone(zone) if zone else "any rooms") + " yet. "
                               "Ask me to inspect a room first.", "data": {}}
        rep = self.store.get_report(reps[0]["id"])
        zones = [z for z in rep.zones if not zone or z.zone == zone]
        when = time.strftime("%H:%M", time.localtime(rep.created))
        day = "today" if time.strftime("%Y%m%d", time.localtime(rep.created)) == time.strftime("%Y%m%d") \
            else time.strftime("%d %b", time.localtime(rep.created))
        parts = []
        for z in zones:
            if z.compliant:
                parts.append(f"{spoken_zone(z.zone)} was all clear")
            else:
                top = "; ".join(short_finding(a.description) for a in z.anomalies[:3])
                n = len(z.anomalies)
                parts.append(f"{spoken_zone(z.zone)} had {n} issue{'s' if n > 1 else ''}: {top}")
        acts = sorted((a for z in zones for a in z.recommended_actions),
                      key=lambda a: {"Critical": 0, "High": 1, "Medium": 2}.get(a["priority"], 3))
        s = f"In my last inspection ({day} at {when}), " + ". ".join(parts) + "."
        if acts:
            s += f" Most urgent: {acts[0]['action'][0].lower()}{acts[0]['action'][1:]}"
        return {"summary": s, "data": {"report_id": rep.id}, "report_id": rep.id}

    async def search_history(self, query: str, zone: str | None = None, days: int | None = None) -> dict:
        if self.memory is None:
            raise ToolError("semantic memory is not available")
        res = await asyncio.to_thread(self.memory.search, query, 5, zone, int(days) if days else None, True,
                                      self.zones())
        hits = res["results"]
        if not hits:
            return {"summary": "No matching inspection records found.", "data": res}
        lines = [f"{h['metadata']['date']} {h['metadata']['zone']}: {h['text'].split('. ', 1)[-1][:160]}" for h in hits]
        return {"summary": f"Found {len(hits)} record(s):\n- " + "\n- ".join(lines), "data": res}

    async def call(self, tool: str, args: dict) -> dict:
        if tool not in TOOL_SPECS:
            raise ToolError(f"unknown tool {tool}")
        fn = getattr(self, tool)
        return await fn(**(args or {}))


def short_finding(desc: str) -> str:
    """'Hot & humid: 29.4°C, 74% RH (target 22-26°C, 40-60% RH)' -> 'hot & humid: 29.4°C, 74% RH'"""
    import re as _re
    d = _re.sub(r"\s*\([^)]*\)", "", desc).strip()
    return d[0].lower() + d[1:] if d and not d[:3].isupper() else d
