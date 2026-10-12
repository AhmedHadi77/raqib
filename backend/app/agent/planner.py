"""Planning: natural language -> list of tool calls.

* LLM planner (GPT-4o / Gemini / Ollama) when configured - returns JSON, validated.
* Rule-based planner otherwise (and as fallback when the LLM output is invalid), so the
  whole system works offline and for free during development.
"""
from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from .llm import extract_json, message_text
from .text import spoken_zone  # noqa: F401 - re-exported
from .tools import TOOL_SPECS

log = logging.getLogger(__name__)


# ------------------------------------------------------------------------- zones
def zone_words(zone: str) -> list[str]:
    return re.sub(r"([a-z])([A-Z][a-z])", r"\1 \2", zone).replace("_", " ").lower().split()


def zone_aliases(zone: str, zones: list[str] | None = None) -> list[str]:
    words = zone_words(zone)
    aliases = {" ".join(words), "".join(words), zone.lower()}
    if len(words) >= 2 and len(words[-1]) <= 2:          # "lecture hall b" -> "hall b"
        aliases.add(" ".join(words[-2:]))
    if zones and len(words) >= 2 and len(words[-1]) > 2:  # "iot lab" -> "the lab" when no other zone ends in "lab"
        others = [z for z in zones if z != zone and zone_words(z)[-1:] == words[-1:]]
        if not others:
            aliases.add("the " + words[-1])
    synonyms = {"lab": ["laboratory"], "hall": ["theatre", "theater"], "room": ["rm"], "home": ["base", "dock",
                                                                                            "charging station"]}
    for a in list(aliases):
        for w, alts in synonyms.items():
            if re.search(rf"\b{w}\b", a):
                for alt in alts:
                    aliases.add(re.sub(rf"\b{w}\b", alt, a))
    return sorted(aliases, key=len, reverse=True)


def find_zones(text: str, zones: list[str]) -> list[str]:
    t = text.lower()
    hits = []
    for z in zones:
        for a in zone_aliases(z, zones):
            m = re.search(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", t)
            if m:
                hits.append((m.start(), z))
                break
    return [z for _, z in sorted(hits)]


# ------------------------------------------------------------------------- numbers in speech
_NUM_WORDS = {"zero": 0, "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
              "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30,
              "forty": 40, "forty-five": 45, "fifty": 50, "sixty": 60, "ninety": 90, "hundred": 100,
              "half a": 0.5, "half": 0.5, "a quarter": 0.25, "quarter": 0.25}


def normalise_numbers(t: str) -> str:
    for w in sorted(_NUM_WORDS, key=len, reverse=True):
        if w in ("a", "an"):
            t = re.sub(rf"\b{w}\s+(?=(meter|metre|foot|step)s?\b)", "1 ", t)
            continue
        t = re.sub(rf"\b{w}\b(?=\s*(cm|centimet|m\b|met|deg|°|percent))", str(_NUM_WORDS[w]), t)
    t = re.sub(r"\b(\d+)\s+(?:and a half|point five)\b", lambda m: str(float(m.group(1)) + 0.5), t)
    return t


# ------------------------------------------------------------------------- rules
HISTORY_RE = re.compile(r"\b(history|historical|past|previous|last (week|month|semester|year)|"
                        r"has .* been|have .* been|how often|show me (all|every)|when was|were there|trend|"
                        r"this (month|week|semester)|ago|search)\b")
INSPECT_RE = re.compile(r"\b(inspect|check|audit|patrol|survey|examine|verify|scan)\b")
STOP_RE = re.compile(r"(please )?(stop|halt|freeze|emergency stop|pause|wait|stay|hold on|stand still|don'?t move)"
                     r"( (now|please|there|here|moving|the robot))*[.!]*")
FINDINGS_RE = re.compile(r"\b(what (did|have) you (find|found|see|seen|discover)|what you (found|find)|"
                         r"(any|the|your|latest|last) (findings|results?|issues|problems)|summar(y|ise|ize)|"
                         r"what happened|how did it go|last (report|inspection)|report back|tell me (the )?result)")
AC_RE = re.compile(r"\b(air ?-?con(d|ditioner|ditioning)?s?|a/?c|ac units?|aircond|air conditioning|cooling|"
                   r"cooler|split units?)\b")
PEOPLE_RE = re.compile(r"\b(anyone|anybody|people|occupied|occupan\w*|empty|someone|somebody|students?|how many)\b")
LIGHTS_RE = re.compile(r"\b(lights?|lamps?|projector|monitors?|screens?|equipment (on|left))\b")
ENV_RE = re.compile(r"\b(temperature|temp|humid\w*|air quality|air|gas|fumes?|comfort|environment|smell|hot|"
                    r"cold|warm|aqi|voc|co2|ventilat\w*)\b")
SOUND_RE = re.compile(r"\b(listen|sound|noise|noisy|hear|audio|alarm|loud)\b")
PHOTO_RE = re.compile(r"\b(photo|picture|snapshot|camera|look around|what do you see|what can you see|show me)\b")
GO_RE = re.compile(r"\b(go|drive|navigate|move|head|take (me|it)|come|travel|run)\b")
HELP_RE = re.compile(r"^(help|what can you do|what do you do|how do i use (you|this)|commands|"
                     r"what (commands|can i say).*)[?.!]*$")
GREET_RE = re.compile(r"^(hi|hello|hey|good (morning|afternoon|evening)|salam|assalamualaikum)( there| robot)?[!.]*$")
THANKS_RE = re.compile(r"^(thanks?( you)?|thank you( very much)?|ok(ay)?|great|good job|nice|cool)[!.]*$")


def quick_reply(text: str) -> str | None:
    """Conversational turns that need no robot action."""
    t = text.lower().strip()
    if GREET_RE.match(t):
        return ("Hello! I'm ready. You can say things like \"Inspect the IoT Lab\", \"Check the aircon in Hall B\", "
                "\"Move forward one meter\" or \"What did you find?\"")
    if THANKS_RE.match(t):
        return "You're welcome. Tell me when you need another check."
    if HELP_RE.match(t):
        return HELP_TEXT
    return None


HELP_TEXT = """Here's what I can do:
- **Inspect rooms** - "Inspect the IoT Lab and Lecture Hall B, then return home", "Patrol all rooms"
- **Check one thing** - "Check the aircon in Hall B", "Is anyone in the lab?", "Are the lights on in Hall A?", "What's the temperature here?"
- **Drive** - "Go to Hall A", "Move forward one meter", "Turn left", "Move right 50 cm", "Turn around", "Come back home", "Stop"
- **Camera** - "Look up", "Look left", "Take a photo", "What do you see?"
- **Results and history** - "What did you find?", "Show me rooms with unhealthy air last month"
- **Status** - "Where are you?", "How is the battery?\""""


def _distance(t: str, default: float | None = None) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(cm|centimet(?:er|re)s?|mm|m\b|met(?:er|re)s?|f(?:oo|ee)t|ft|steps?)", t)
    if m:
        v, u = float(m.group(1)), m.group(2)
        if u.startswith("c"):
            return v / 100.0
        if u == "mm":
            return v / 1000.0
        if u.startswith("f"):
            return v * 0.3048
        if u.startswith("step"):
            return v * 0.3
        return v
    if re.search(r"\b(a (little|bit)|slightly|a few)\b", t):
        return 0.25
    return default


MON_STOP_RE = re.compile(r"\b(stop|end|finish|cancel|quit|turn off)\b.{0,25}\b(monitor\w*|invigilat\w*|exam mode|watching|proctor\w*)")
MON_STATUS_RE = re.compile(r"\b(how('s| is) the exam( going)?|monitor\w* status|any (incidents|talking|noise)|"
                           r"who (has been|was) talking|how many (times|incidents))\b")
MON_START_RE = re.compile(r"\b(monitor|invigilat\w*|supervise|proctor\w*|watch over|keep watch|guard)\b|\bexam mode\b|"
                          r"\b(watch|look|check) (for|out for) (cheat\w*|phones?|cheaters?)\b|\bcatch (cheat\w*|cheaters?)\b")
FIND_SOUND_RE = re.compile(r"\b(who|anyone|someone|somebody|which|where)\b.{0,30}\b(talk\w*|speak\w*|chat\w*|whisper\w*|"
                           r"noise|sound|voice)|\b(find|locate|go (to|near|toward|towards)|follow)\b.{0,20}\b(the )?"
                           r"(noise|sound|voice|talking|speaker|person talking)")
HUSH_RE = re.compile(r"\b(tell|ask|warn)\b.{0,20}\b(them|students?|him|her|everyone|people|whoever)\b.{0,25}"
                     r"\b(stop talking|be quiet|quiet|silent|silence|keep it down)|\bstop talking\b|\bbe quiet\b")
DESCRIBE_RE = re.compile(r"\b(what (do|can) you see|what('s| is) (in front|ahead|there|that|this|it)|what are you looking at|"
                         r"describe|identify|tell me what (it|that|this|you see)|what('s| is) (around|near) you|"
                         r"look (around|ahead)|recogni[sz]e)\b")
MINUTES_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(min|mins|minutes|hour|hours|hr|hrs|h)\b")


def _plan_clause(text: str, zones: list[str], context_zone: str | None = None) -> list[dict]:
    t = normalise_numbers(text.lower().strip())
    room_zones = [z for z in zones if z.lower() != "home"]
    mentioned = find_zones(t, zones)
    if not mentioned and context_zone and re.search(r"\b(there|that room|that place|it again|same room)\b", t):
        mentioned = [context_zone]
    rooms = [z for z in mentioned if z.lower() != "home"]

    if MON_STOP_RE.search(t):
        return [{"tool": "stop_monitoring", "args": {}}]
    if STOP_RE.fullmatch(t):
        return [{"tool": "stop", "args": {}}]
    if MON_STATUS_RE.search(t):
        return [{"tool": "monitor_status", "args": {}}]
    if MON_START_RE.search(t) and not re.search(r"\b(air ?con|temperature|ac)\b", t):
        m = MINUTES_RE.search(t)
        mins = 60.0
        if m:
            mins = float(m.group(1)) * (60 if m.group(2).startswith("h") else 1)
        sens = "high" if re.search(r"\b(strict|sensitive|any whisper|high)\b", t) else \
            "low" if re.search(r"\b(relaxed|low|only loud)\b", t) else "normal"
        args = {"minutes": mins, "sensitivity": sens}
        if re.search(r"\b(stay|stand|wait|don'?t move|do not move|from the (front|middle|centre|center)|in one place)\b", t):
            args["mode"] = "stay"
        elif re.search(r"\b(patrol|walk|go around|move around|round the|around the (class|room|hall))\b", t):
            args["mode"] = "patrol"
        if rooms:
            args["zone"] = rooms[0]
        return [{"tool": "start_monitoring", "args": args}]
    if FIND_SOUND_RE.search(t) or HUSH_RE.search(t):
        return [{"tool": "find_sound", "args": {"warn": bool(HUSH_RE.search(t))}}]
    if FINDINGS_RE.search(t) and not INSPECT_RE.search(t.replace("check", "")):
        return [{"tool": "last_findings", "args": {"zone": rooms[0]} if rooms else {}}]
    if HISTORY_RE.search(t) and not re.search(r"\b(now|right now|currently)\b", t):
        return [{"tool": "search_history", "args": {"query": text}}]

    steps: list[dict] = []
    full_inspect = re.search(r"\b(inspect|audit|patrol|survey|full (check|inspection)|everything)\b", t)

    # ---- focused checks: "check the aircon in Hall B", "is anyone in the lab", "temperature in hall A"
    if AC_RE.search(t) and not full_inspect:
        if not rooms and re.search(r"\b(all|every|each)\b", t):
            rooms = room_zones
        for z in rooms or [None]:
            steps.append({"tool": "check_ac", "args": {"zone": z} if z else {}})
    elif not full_inspect and rooms and (PEOPLE_RE.search(t) or LIGHTS_RE.search(t) or ENV_RE.search(t)
                                         or SOUND_RE.search(t) or PHOTO_RE.search(t)):
        for z in rooms:
            steps.append({"tool": "go_to_zone", "args": {"zone": z}})
            if PEOPLE_RE.search(t) or LIGHTS_RE.search(t) or PHOTO_RE.search(t):
                focus = "people" if PEOPLE_RE.search(t) else "lights, projector and screens" if LIGHTS_RE.search(t) else text
                steps.append({"tool": "capture_and_analyze", "args": {"focus": focus}})
            if ENV_RE.search(t):
                steps.append({"tool": "read_environment", "args": {}})
            if SOUND_RE.search(t):
                steps.append({"tool": "listen_audio", "args": {}})
    elif INSPECT_RE.search(t) or full_inspect:
        targets = rooms
        if not targets and re.search(r"\b(all|every|patrol|each|everything|whole|building|floor)\b", t):
            targets = room_zones
        for z in targets:
            steps.append({"tool": "inspect_zone", "args": {"zone": z}})

    # ---- navigation to a named place
    if not steps and mentioned and GO_RE.search(t):
        z = mentioned[0]
        steps.append({"tool": "return_home", "args": {}} if z.lower() == "home" else {"tool": "go_to_zone", "args": {"zone": z}})

    # ---- "go 5 meters" with no direction = forward
    if not steps and not mentioned and GO_RE.search(t) and _distance(t) is not None and \
            not re.search(r"\b(back|backward|backwards|reverse|left|right)\b", t):
        steps.append({"tool": "move", "args": {"distance_m": round(_distance(t), 2)}})

    # ---- relative motion: "move forward 1 m", "move left 50 cm", "turn right", "turn around"
    if not any(s["tool"] in ("go_to_zone", "inspect_zone", "check_ac", "return_home", "move") for s in steps):
        side = re.search(r"\b(?:move|go|drive|step|shift|slide)\s+(?:to the\s+)?(left|right)\b", t)
        straight = re.search(r"\b(forward|forwards|ahead|straight|back(?:ward)?s?|reverse|backup|back up)\b", t)
        turn = re.search(r"\b(?:turn|rotate|face)(?:\s+(?:to the|by))?\s+(left|right|around)\b", t) or \
            re.search(r"\b(u-?turn|spin around|about face|turn around)\b", t)
        if side:
            d = _distance(t, 0.5)
            sgn = 1.0 if side.group(1) == "left" else -1.0
            steps += [{"tool": "turn", "args": {"angle_deg": 90.0 * sgn}},
                      {"tool": "move", "args": {"distance_m": round(d, 2)}}]
        elif straight and re.search(r"\b(move|go|drive|come|back|reverse|forward|ahead|step|backup)\b", t) \
                and not re.search(r"\b(come back|go back home|back home|return)\b", t):
            d = _distance(t, 0.5)
            back = straight.group(1).startswith(("back", "rev"))
            steps.append({"tool": "move", "args": {"distance_m": round(-d if back else d, 2)}})
        if turn and not side:
            g = turn.group(1) if turn.lastindex else turn.group(0)
            ang_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:deg|degrees|°)?", t[turn.end():turn.end() + 16])
            if g in ("left", "right"):
                ang = float(ang_m.group(1)) if ang_m else 90.0
                steps.insert(0 if not straight else len(steps),
                             {"tool": "turn", "args": {"angle_deg": ang if g == "left" else -ang}})
            else:
                steps.append({"tool": "turn", "args": {"angle_deg": 180.0}})
        elif re.search(r"\bspin\b", t) and not steps:
            steps.append({"tool": "turn", "args": {"angle_deg": 360.0}})

    # ---- camera pointing
    look = re.search(r"\blook(?:ing)?\s+(up|down|left|right|ahead|straight|forward|at the ceiling|at the floor)\b", t)
    if look:
        pan, tilt = {"up": (0, 35), "at the ceiling": (0, 55), "down": (0, -25), "at the floor": (0, -40),
                     "left": (60, 10), "right": (-60, 10)}.get(look.group(1), (0, 10))
        steps.append({"tool": "pan_tilt", "args": {"pan": pan, "tilt": tilt}})

    # ---- sensing in place
    if not any(s["tool"] in ("inspect_zone", "check_ac") for s in steps) and not rooms:
        if DESCRIBE_RE.search(t):
            steps.append({"tool": "capture_and_analyze", "args": {"focus": "describe: " + text}})
        elif PHOTO_RE.search(t) or PEOPLE_RE.search(t) or (LIGHTS_RE.search(t) and not steps):
            focus = "people" if PEOPLE_RE.search(t) else "describe: " + text
            steps.append({"tool": "capture_and_analyze", "args": {"focus": focus}})
        if ENV_RE.search(t) and not re.search(r"\bair ?con", t):
            steps.append({"tool": "read_environment", "args": {}})
        if SOUND_RE.search(t):
            steps.append({"tool": "listen_audio", "args": {}})

    if re.search(r"\b(come back|return|go home|back home|return home|go back to base|dock)\b", t) and not any(
            s["tool"] == "return_home" for s in steps):
        steps.append({"tool": "return_home", "args": {}})
    m = re.search(r"\b(say|announce|tell (them|everyone|the room))\s+[\"']?(.+?)[\"']?$", text, re.I)
    if m and not steps:
        steps.append({"tool": "speak", "args": {"text": m.group(3)}})
    if not steps and re.search(r"\b(status|battery|where are you|where're you|state|how are you|location|charge)\b", t):
        steps.append({"tool": "get_status", "args": {}})
    return steps[:12]


ACTION_RE = re.compile(r"\b(go|move|drive|head|come|return|turn|rotate|spin|face|look|take|snap|capture|photograph|"
                       r"tell|say|announce|ask|warn|check|inspect|audit|patrol|scan|listen|find|locate|search|show|what|"
                       r"who|where|is|are|how|stop|wait|pause|monitor|watch|invigilat\w*|describe|identify|read|"
                       r"measure|report|back up|reverse|follow|guard)\b")
SPLIT_RE = re.compile(r"\s*(?:,|;|\.\s+|\band then\b|\bthen\b|\bafter that\b|\bafterwards\b|\bnext\b|\band\b)\s*")


def split_clauses(text: str) -> list[str]:
    """'go 5 m, take a picture and tell me what it is' -> ['go 5 m', 'take a picture', 'tell me what it is'].
    A fragment without an action word belongs to the clause before it ('inspect the lab and hall B')."""
    clauses: list[str] = []
    for part in SPLIT_RE.split(text.strip().rstrip(".!?")):
        part = (part or "").strip()
        if not part:
            continue
        if clauses and not ACTION_RE.search(part.lower()):
            clauses[-1] += " and " + part
        else:
            clauses.append(part)
    return clauses


def rule_plan(text: str, zones: list[str], context_zone: str | None = None) -> list[dict]:
    """Plan each clause in order, so any chain of known actions works."""
    clauses = split_clauses(text)
    if len(clauses) <= 1:
        return _plan_clause(text, zones, context_zone)
    steps: list[dict] = []
    ctx = context_zone
    for c in clauses:
        part = _plan_clause(c, zones, ctx)
        if not part and len(c.split()) <= 3:
            continue
        for st in part:
            prev = steps[-1] if steps else None
            # "take a picture and tell me what it is" = one photo with the question attached
            if prev and prev["tool"] == st["tool"] == "capture_and_analyze":
                prev["args"]["focus"] = st["args"].get("focus") or prev["args"].get("focus")
                continue
            # "go to the noise and tell them to stop talking" = one search, with the warning
            if prev and prev["tool"] == st["tool"] == "find_sound":
                prev["args"]["warn"] = prev["args"].get("warn") or st["args"].get("warn")
                continue
            if prev and prev == st and st["tool"] in ("return_home", "stop", "get_status"):
                continue
            steps.append(st)
            z = st["args"].get("zone")
            if z:
                ctx = z
    if not steps:
        return _plan_clause(text, zones, context_zone)
    return steps[:12]


def plan_ack(plan: list[dict]) -> str | None:
    """Short spoken acknowledgement read out as soon as the plan is ready (long missions only)."""
    moving = [s for s in plan if s["tool"] in ("inspect_zone", "go_to_zone", "return_home", "check_ac", "move", "turn",
                                               "find_sound")]
    if not moving:
        return None
    parts: list[str] = []
    if any(s["tool"] == "find_sound" for s in plan):
        parts.append("find who is talking" + (" and ask them to stop" if any(s["args"].get("warn") for s in plan
                                                                            if s["tool"] == "find_sound") else ""))
    long_moves = [s for s in plan if s["tool"] == "move" and abs(float(s["args"].get("distance_m", 0))) >= 3]
    if long_moves:
        parts.append(f"drive {abs(float(long_moves[0]['args']['distance_m'])):g} m "
                     f"{'forward' if long_moves[0]['args']['distance_m'] > 0 else 'back'}, stopping if anything is in the way")
    insp = [spoken_zone(s["args"].get("zone")) for s in plan if s["tool"] == "inspect_zone"]
    if insp:
        parts.append("inspect " + _join(insp))
    acs = [s for s in plan if s["tool"] == "check_ac"]
    if acs:
        z = [spoken_zone(s["args"]["zone"]) for s in acs if s["args"].get("zone")]
        parts.append("check the air-conditioning" + (" in " + _join(z) if z else " here"))
    gos = [spoken_zone(s["args"].get("zone")) for s in plan if s["tool"] == "go_to_zone"]
    if gos and not insp and not acs:
        parts.append("head to " + _join(gos))
    if any(s["tool"] in ("move", "turn") for s in plan) and not parts:
        return None   # short manoeuvres: just do it
    home = any(s["tool"] == "return_home" for s in plan)
    if not parts:
        return "On it. Heading back home." if home else None
    return "On it. I'll " + _join(parts) + (", then return home." if home else ".")


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


# ------------------------------------------------------------------------- LLM
PLANNER_PROMPT = """You are the planner of InspectionAgent, the brain of a mobile campus inspection robot.
Convert the operator's request into a short ordered list of tool calls.

Known zones (use these exact names): {zones}
The zone the operator talked about last (for "there", "that room"): {context}

Tools:
{tools}

Rules:
- Break ANY request into the tools above, in the order the operator said them. Distances are in metres
  (convert cm, steps x 0.3). "Go 5 m and take a picture and tell me what it is" = move 5, then
  capture_and_analyze with focus "describe: tell me what it is".
- "What do you see / what is that / describe" -> capture_and_analyze with the question as the focus.
- "Who is talking / find the noise" -> find_sound; add warn=true when they should be told to stop talking.
- "Monitor / invigilate / proctor the exam in <room> for N minutes", "watch for cheating" -> start_monitoring
  (mode "stay" if told to stay in one place, else "patrol"); "stop monitoring" -> stop_monitoring;
  "how is the exam going" -> monitor_status.
- "Say / announce X" -> speak.
- To inspect / audit a whole room use inspect_zone (it already covers vision, temperature, gas and sound).
- For a focused question use the focused tool: air-conditioner -> check_ac; "is anyone there" / lights -> go_to_zone
  then capture_and_analyze with a focus; temperature -> go_to_zone then read_environment.
- "What did you find", "results", "summary" -> last_findings.
- "Move left/right X" = turn 90 degrees that way, then move X. Positive turn angle = left.
- Questions about the PAST (history, trends, last month, how often) -> search_history only, do not drive.
- Use at most 12 steps. Never invent zones.
- If the request needs no robot action (greeting, general question) return an empty list and put your answer in "reply".
- If it asks for something the robot physically cannot do (stairs, opening doors, leaving the building), return an
  empty list and explain briefly in "reply" what you can do instead.
Answer ONLY with JSON: {{"steps": [{{"tool": "<name>", "args": {{...}}}}], "reply": "<optional text>"}}"""


async def llm_plan(model, text: str, zones: list[str], context_zone: str | None = None) -> tuple[list[dict], str | None]:
    tools = "\n".join(f"- {n}({', '.join(f'{k}: {v}' for k, v in s['args'].items())}): {s['desc']}"
                      for n, s in TOOL_SPECS.items())
    msgs = [SystemMessage(content=PLANNER_PROMPT.format(zones=", ".join(zones) or "(unknown)", tools=tools, context=context_zone or "none")),
            HumanMessage(content=text)]
    resp = await model.ainvoke(msgs)
    data = extract_json(message_text(resp))
    if isinstance(data, list):
        data = {"steps": data}
    steps = []
    for s in data.get("steps", [])[:12]:
        if s.get("tool") in TOOL_SPECS:
            steps.append({"tool": s["tool"], "args": s.get("args") or {}})
        else:
            log.warning("LLM proposed unknown tool %s - dropped", s.get("tool"))
    return steps, data.get("reply")


async def summarize_with_llm(model, request: str, observations: list[dict]) -> str | None:
    try:
        msgs = [SystemMessage(content="You are InspectionAgent, a facility inspection robot. Answer the operator "
                                      "in a friendly, spoken style (max 5 short sentences, no markdown) using ONLY the tool observations provided. "
                                      "Mention concrete numbers, dates and zones. Do not invent facts."),
                HumanMessage(content=f"Request: {request}\n\nObservations:\n{json.dumps(observations, default=str)[:12000]}")]
        return message_text(await model.ainvoke(msgs)).strip()
    except Exception as e:  # noqa: BLE001
        log.warning("LLM summary failed: %s", e)
        return None
