"""FastAPI backend - REST + WebSocket API for the mobile app.

Run (dev):   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
API docs:    http://localhost:8000/docs
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import auth as auth_mod
from .agent.graph import InspectionAgent
from .auth import ROLE_LEVEL, authenticate, create_token, current_user, decode_token, require_role
from .config import BACKEND_DIR, get_settings
from .memory import SemanticMemory
from .mqtt_bridge import RobotBridge
from .schemas import (ChatRequest, ChatResponse, CommandRequest, LoginRequest, PasswordChange, ScheduleIn,
                      TokenResponse, UserIn, UserPatch, WebRTCOffer)
from .store import Store
from .stt import SpeechToText, STTUnavailable

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
log = logging.getLogger("backend")
settings = get_settings()

ADMIN_ACTIONS = {"set_privacy", "set_home"}
VIEWER_ACTIONS = {"estop", "ping", "status"}


class Hub:
    """WebSocket fan-out of telemetry, robot events and agent progress."""

    def __init__(self):
        self.clients: dict[WebSocket, dict] = {}

    async def send_all(self, msg: dict):
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_json(msg)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.clients.pop(ws, None)

    async def send_user(self, username: str, msg: dict):
        for ws, user in list(self.clients.items()):
            if user.get("sub") == username:
                try:
                    await ws.send_json(msg)
                except Exception:  # noqa: BLE001
                    self.clients.pop(ws, None)


class AppState:
    bridge: RobotBridge
    store: Store
    memory: SemanticMemory | None = None
    memory_error: str | None = None
    agent: InspectionAgent
    hub: Hub
    stt: SpeechToText
    broker = None
    frame_cache: dict = {}


S = AppState()


async def _init_memory():
    try:
        S.memory = await asyncio.to_thread(SemanticMemory, settings)
        S.agent.memory = S.memory
        log.info("Semantic memory ready (%s, %d records)", S.memory.backend, S.memory.count())
    except Exception as e:  # noqa: BLE001
        S.memory_error = str(e)
        log.exception("Semantic memory unavailable")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.embedded_broker:
        from .dev_broker import start_broker

        S.broker = await start_broker(settings.mqtt_port)
    S.store = Store(settings.data_dir)
    S.store.seed_users(settings.user_table)
    auth_mod.USER_STORE = S.store
    S.stt = SpeechToText(settings)
    S.hub = Hub()
    S.bridge = RobotBridge(settings)
    S.bridge.listeners.add(S.hub.send_all)
    await S.bridge.start()
    S.agent = InspectionAgent(settings, S.bridge, None, S.store)
    S.agent.monitor.notify = S.hub.send_all
    S.bridge.listeners.add(_wiring_listener)
    log.info("Planner: %s | VLM: %s | Voice: %s", S.agent.planner_name, S.agent.vision.name, S.stt.name)
    mem_task = asyncio.create_task(_init_memory())
    stt_task = asyncio.create_task(S.stt.warm_up())
    sched_task = asyncio.create_task(_scheduler())
    tasks = [mem_task, stt_task, sched_task]
    if settings.discovery_beacon:
        from .discovery import beacon_loop

        tasks.append(asyncio.create_task(beacon_loop(settings, settings.api_port)))
    yield
    for t in tasks:
        t.cancel()
    await S.bridge.stop()
    if S.broker:
        await S.broker.shutdown()


APP_VERSION = "2.3.0"
app = FastAPI(title=f"{settings.product_name} - AI Inspection Robot API", version=APP_VERSION, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
                   allow_methods=["*"], allow_headers=["*"])


# App pages whose address is also an API endpoint (/reports, /health, /users, /schedules).
# A browser opening the page (Accept: text/html) gets the web app; fetch() calls get JSON.
_SPA_PAGES = {"/", "/drive", "/chat", "/reports", "/more", "/insights", "/schedules", "/health", "/users",
              "/settings", "/login", "/scan", "/monitor", "/ai"}


@app.middleware("http")
async def spa_pages(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if (request.method == "GET" and "text/html" in request.headers.get("accept", "")
            and (path in _SPA_PAGES or (path.startswith("/report/") and path.count("/") == 2))):
        index = BACKEND_DIR / "webapp" / "index.html"
        if index.exists():
            return FileResponse(index, media_type="text/html", headers={"Cache-Control": "no-cache"})
    return await call_next(request)


def _robot(robot_id: str):
    if robot_id not in S.bridge.robots:
        raise HTTPException(404, f"unknown robot {robot_id}")
    return S.bridge.robots[robot_id]


# ======================================================================= public
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "raqib",
        "mqtt_connected": S.bridge.connected,
        "robots": {rid: r.summary() for rid, r in S.bridge.robots.items()},
        "planner": S.agent.planner_name,
        "vlm": S.agent.vision.name,
        "stt": S.stt.name,
        "proctor": _proctor_info(),
        "warnings": _warnings(),
        "version": APP_VERSION,
        "product": settings.product_name,
        "site": settings.site_name,
        "memory": {"ready": S.memory is not None, "backend": S.memory.backend if S.memory else None,
                   "records": S.memory.count() if S.memory else 0, "error": S.memory_error},
        "time": time.time(),
    }


def _warnings() -> list[str]:
    out = []
    real = [rid for rid, r in S.bridge.robots.items() if (r.telemetry or {}).get("simulation") is False]
    if real and S.agent.vision.name == "mock":
        out.append("The real robot is connected but no vision AI is set: photos are saved but not analysed. "
                   "Set VLM_PROVIDER and an API key (or Ollama) in backend/.env.")
    if "change-me" in settings.jwt_secret.lower():
        out.append("JWT_SECRET is still the default. Set a long random value in backend/.env before going live.")
    return out


@app.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    role = authenticate(body.username, body.password)
    if not role:
        S.store.audit(body.username, "login_failed")
        raise HTTPException(401, "invalid username or password")
    token, exp = create_token(body.username, role)
    S.store.audit(body.username, "login")
    S.store.update_user(body.username, last_login=time.time())
    u = S.store.get_user(body.username) or {}
    return TokenResponse(access_token=token, role=role, username=body.username, expires_in=exp,
                         name=u.get("name") or body.username)


@app.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    u = S.store.get_user(user["sub"]) or {}
    return {"username": user["sub"], "role": user["role"], "name": u.get("name") or user["sub"]}


@app.post("/auth/password")
async def change_password(body: PasswordChange, user: dict = Depends(current_user)):
    if not authenticate(user["sub"], body.current_password):
        raise HTTPException(400, "current password is wrong")
    S.store.update_user(user["sub"], password=body.new_password)
    S.store.audit(user["sub"], "password_changed")
    return {"ok": True}


# ======================================================================= users (admin)
@app.get("/users")
async def users_list(user: dict = Depends(require_role("admin"))):
    return S.store.list_users()


@app.post("/users")
async def users_create(body: UserIn, user: dict = Depends(require_role("admin"))):
    if S.store.get_user(body.username):
        raise HTTPException(409, "that username already exists")
    S.store.create_user(body.username, body.password, body.role, body.name)
    S.store.audit(user["sub"], "user_created", {"username": body.username, "role": body.role})
    return {"ok": True}


@app.patch("/users/{username}")
async def users_update(username: str, body: UserPatch, user: dict = Depends(require_role("admin"))):
    u = S.store.get_user(username)
    if not u:
        raise HTTPException(404, "no such user")
    demoting = u["role"] == "admin" and ((body.role and body.role != "admin") or body.disabled)
    if demoting and S.store.count_admins() <= 1:
        raise HTTPException(400, "at least one active admin is required")
    S.store.update_user(username, role=body.role, name=body.name, password=body.password, disabled=body.disabled)
    S.store.audit(user["sub"], "user_updated", {"username": username, **body.model_dump(exclude={"password"},
                                                                                         exclude_none=True)})
    return {"ok": True}


@app.delete("/users/{username}")
async def users_delete(username: str, user: dict = Depends(require_role("admin"))):
    if username == user["sub"]:
        raise HTTPException(400, "you cannot delete your own account")
    u = S.store.get_user(username)
    if u and u["role"] == "admin" and S.store.count_admins() <= 1:
        raise HTTPException(400, "at least one active admin is required")
    S.store.delete_user(username)
    S.store.audit(user["sub"], "user_deleted", {"username": username})
    return {"ok": True}


# ======================================================================= voice
# ======================================================================= virtual wiring (Wiring Bench)
WIRING_FILE = Path(settings.data_dir) / "wiring.json"


def _wiring_saved() -> dict:
    try:
        return json.loads(WIRING_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"enabled": False, "wires": {}}


async def _wiring_listener(msg: dict):
    """When a simulated robot (re)connects, give it the wiring saved on the bench."""
    if msg.get("kind") != "info" or not (msg.get("data") or {}).get("virtual_wiring"):
        return
    saved = _wiring_saved()
    if saved.get("enabled") or saved.get("wires"):
        await asyncio.sleep(1.0)
        await S.bridge.send(msg["robot_id"], "set_wiring", {"enabled": bool(saved.get("enabled")), "wires": saved.get("wires", {})},
                            timeout=10, issued_by="wiring-bench")


@app.get("/wiring/spec")
async def wiring_spec(robot_id: str | None = None, user: dict = Depends(require_role("viewer"))):
    ack = await S.bridge.send(robot_id or settings.robot_id, "wiring_spec", {}, timeout=10, issued_by=user["sub"])
    if ack.status != "ok":
        raise HTTPException(409, ack.error or "the robot is not connected")
    return ack.result


@app.get("/wiring")
async def wiring_get(robot_id: str | None = None, user: dict = Depends(require_role("viewer"))):
    saved = _wiring_saved()
    ack = await S.bridge.send(robot_id or settings.robot_id, "wiring_status", {}, timeout=10, issued_by=user["sub"])
    return {"saved": saved, "robot": ack.result if ack.status == "ok" else None,
            "robot_error": None if ack.status == "ok" else (ack.error or ack.status)}


@app.put("/wiring")
async def wiring_put(body: dict, robot_id: str | None = None, user: dict = Depends(require_role("operator"))):
    wires = {str(k): str(v) for k, v in (body.get("wires") or {}).items() if v}
    saved = {"enabled": bool(body.get("enabled")), "wires": wires, "updated": time.time(), "by": user["sub"]}
    WIRING_FILE.write_text(json.dumps(saved), encoding="utf-8")
    ack = await S.bridge.send(robot_id or settings.robot_id, "set_wiring", {"enabled": saved["enabled"], "wires": wires},
                              timeout=10, issued_by=user["sub"])
    return {"saved": saved, "robot": ack.result if ack.status == "ok" else None,
            "robot_error": None if ack.status == "ok" else (ack.error or ack.status)}


@app.get("/bench", response_class=HTMLResponse)
async def wiring_bench_page():
    return FileResponse(Path(__file__).parent / "static" / "bench.html", media_type="text/html")


# ======================================================================= AI settings (admin)
def _ai_active() -> dict:
    return {"planner": S.agent.planner_name, "vision": S.agent.vision.name, "voice": S.stt.name}


@app.get("/admin/ai")
async def ai_get(user: dict = Depends(require_role("admin"))):
    from . import ai_settings

    return ai_settings.current(settings, _ai_active())


@app.put("/admin/ai")
async def ai_put(body: dict, user: dict = Depends(require_role("admin"))):
    """Save the AI provider / key into backend/.env and switch over immediately (no restart)."""
    from . import ai_settings
    from .agent.llm import get_chat_model
    from .vlm import VisionAnalyzer

    try:
        env = ai_settings.apply(settings, body)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    try:
        ai_settings.write_env(env)
        saved = True
    except OSError as e:
        log.warning("could not write backend/.env: %s", e)
        saved = False
    S.agent.llm = get_chat_model(settings)
    S.agent.vision = VisionAnalyzer(settings)
    S.stt = SpeechToText(settings)
    asyncio.create_task(S.stt.warm_up())
    S.store.audit(user["sub"], "ai_settings", {k: ("set" if "KEY" in k and v else v) for k, v in env.items()})
    out = ai_settings.current(settings, _ai_active())
    out["saved"] = saved
    return out


@app.post("/admin/ai/test")
async def ai_test(user: dict = Depends(require_role("admin"))):
    """Ask the planner model to plan a sample order - proves the key / Ollama works."""
    from .agent.planner import llm_plan

    if S.agent.llm is None:
        return {"ok": False, "error": "No AI model is active. Choose Gemini, OpenAI or Ollama and save first."}
    t0 = time.time()
    zones = _zones() or ["IoT_Lab", "Exam_Hall"]
    try:
        plan, reply = await asyncio.wait_for(
            llm_plan(S.agent.llm, "please wander over to the lab and tell me if anybody left a laptop there", zones), 45)
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        hint = ("The key was rejected (copy it again from the provider's page) or this PC can't reach the provider." if re.search(r"401|403|API key|api_key|permission", msg, re.I)
                else "Ollama isn't running: start it, or run 'ollama serve'." if "11434" in msg or "Connection refused" in msg
                else "The free quota is used up for now: wait a minute and try again." if re.search(r"429|quota|rate", msg, re.I)
                else "")
        return {"ok": False, "error": (hint + " " if hint else "") + msg[:300], "seconds": round(time.time() - t0, 1)}
    steps = ", ".join(p["tool"] + ("(" + ", ".join(f"{k}={v}" for k, v in p.get("args", {}).items()) + ")" if p.get("args") else "")
                      for p in plan)
    return {"ok": True, "seconds": round(time.time() - t0, 1), "model": S.agent.planner_name,
            "sample": "please wander over to the lab and tell me if anybody left a laptop there",
            "plan": steps or None, "reply": reply}


@app.post("/voice/transcribe")
async def voice_transcribe(request: Request, user: dict = Depends(require_role("operator"))):
    """Speech -> text. Body: multipart form field 'file', or the raw audio bytes (Content-Type audio/*)."""
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/"):
        form = await request.form()
        f = form.get("file")
        if f is None or isinstance(f, str):
            raise HTTPException(400, "missing 'file' field")
        data, filename, mime = await f.read(), f.filename or "voice.m4a", f.content_type or "audio/mp4"
    else:
        data, filename, mime = await request.body(), "voice.webm", ctype or "audio/webm"
    try:
        out = await S.stt.transcribe(data, filename, mime, zones=_zones())
    except STTUnavailable as e:
        raise HTTPException(501, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("transcription failed")
        raise HTTPException(502, f"speech recognition failed: {e}") from e
    S.store.audit(user["sub"], "voice", {"text": out["text"], "ms": out["ms"]})
    return out


def _zones(robot_id: str | None = None) -> list[str]:
    r = S.bridge.robots.get(robot_id or settings.robot_id)
    return list(((r.info or {}).get("zones") or {}).keys()) if r else []


# ======================================================================= exam monitoring
@app.get("/monitor")
async def monitor_status(user: dict = Depends(require_role("viewer"))):
    st = S.agent.monitor.status()
    st.pop("_hfov", None)
    return {**st, "text": S.agent.monitor.describe()}


@app.post("/monitor/start")
async def monitor_start(body: dict, user: dict = Depends(require_role("operator"))):
    zone = body.get("zone") or None
    zones = _zones(body.get("robot_id"))
    if zone and zones and zone not in zones:
        raise HTTPException(400, f"unknown room {zone}")
    S.store.audit(user["sub"], "monitor_start", body)
    text = await S.agent.monitor.start(body.get("robot_id") or settings.robot_id, zone, float(body.get("minutes") or 60),
                                       str(body.get("sensitivity") or "normal"), user["sub"],
                                       mode=str(body.get("mode") or "patrol"),
                                       detect=body.get("detect") if isinstance(body.get("detect"), dict) else None)
    return {"text": text, **S.agent.monitor.status()}


@app.get("/monitor/sessions")
async def monitor_sessions(user: dict = Depends(require_role("viewer"))):
    return S.store.list_exam_sessions()


@app.get("/monitor/sessions/{sid}")
async def monitor_session(sid: str, user: dict = Depends(require_role("viewer"))):
    sess = S.store.get_exam_session(sid)
    if not sess:
        raise HTTPException(404, "session not found")
    return sess


@app.get("/monitor/sessions/{sid}/print", response_class=HTMLResponse)
async def monitor_session_print(sid: str, user: dict = Depends(require_role("viewer"))):
    from .report import render_exam_html

    sess = S.store.get_exam_session(sid)
    if not sess:
        raise HTTPException(404, "session not found")
    return HTMLResponse(render_exam_html(sess, settings.data_dir, settings.product_name, settings.site_name))


def _proctor_info() -> dict:
    from .proctor import MediaPipeProctor

    mode = settings.proctor_vision
    mp = MediaPipeProctor.available()
    ai = S.agent.vision.model is not None
    real = any((r.telemetry or {}).get("simulation") is False for r in S.bridge.robots.values())
    if mode == "off":
        text = "Camera checks are off (PROCTOR_VISION=off). Sound checks still work."
    elif mp:
        text = "Head turns, looking down and phones are checked on this PC with MediaPipe" + \
            (", and the vision AI also looks for notes and earpieces." if ai else
             ". Add a vision AI in AI settings to also spot notes and earpieces.")
    elif ai:
        text = "The vision AI checks each view for phones, notes, earpieces and heads turned (about every 8 s)."
    else:
        text = "Camera checks need MediaPipe (run upgrade.bat) or a vision AI (More > AI settings). Sound checks work now."
    sim = any((r.telemetry or {}).get("simulation") for r in S.bridge.robots.values())
    if sim and not real and mode != "off":
        text = "Simulator: it knows what each student is doing, so every check works. With the real robot: " + text[0].lower() + text[1:]
    return {"mode": mode, "mediapipe": mp, "vision_ai": ai, "text": text}


@app.get("/monitor/capabilities")
async def monitor_capabilities(user: dict = Depends(require_role("viewer"))):
    return _proctor_info()


@app.post("/monitor/stop")
async def monitor_stop(user: dict = Depends(require_role("operator"))):
    S.store.audit(user["sub"], "monitor_stop")
    return {"text": await S.agent.monitor.stop("stopped by " + user["sub"])}


# ======================================================================= scheduled patrols
@app.get("/schedules")
async def schedules_list(user: dict = Depends(require_role("viewer"))):
    return S.store.list_schedules()


@app.post("/schedules")
async def schedules_save(body: ScheduleIn, user: dict = Depends(require_role("operator"))):
    sched = S.store.save_schedule(body.model_dump(), user["sub"])
    S.store.audit(user["sub"], "schedule_saved", {"id": sched["id"], "name": body.name, "time": body.time})
    return sched


@app.post("/schedules/{sid}/enabled")
async def schedules_enable(sid: str, enabled: bool = True, user: dict = Depends(require_role("operator"))):
    S.store.set_schedule_enabled(sid, enabled)
    return {"ok": True}


@app.delete("/schedules/{sid}")
async def schedules_delete(sid: str, user: dict = Depends(require_role("operator"))):
    S.store.delete_schedule(sid)
    S.store.audit(user["sub"], "schedule_deleted", {"id": sid})
    return {"ok": True}


@app.post("/schedules/{sid}/run")
async def schedules_run_now(sid: str, user: dict = Depends(require_role("operator"))):
    sched = S.store.get_schedule(sid)
    if not sched:
        raise HTTPException(404, "no such schedule")
    if S.agent.lock.locked():
        raise HTTPException(409, "the robot is busy with another mission")
    asyncio.create_task(_run_schedule(sched, f"manual-{int(time.time())}"))
    return {"ok": True}


async def _run_schedule(sched: dict, key: str):
    S.store.mark_schedule(sched["id"], key=key)
    rid = sched.get("robot_id") or settings.robot_id
    who = f"schedule:{sched['name']}"
    try:
        resp = await S.agent.run(sched["command"], rid, who)
        failed = any(st.status == "error" for st in resp.steps)
        S.store.mark_schedule(sched["id"], status="error" if failed else "ok", report=resp.report_id)
        S.store.save_chat(who, sched["command"], resp.reply, resp.report_id)
        if resp.report_id:
            rep = S.store.get_report(resp.report_id)
            issues = sum(len(z.anomalies) for z in rep.zones) if rep else 0
            await S.hub.send_all({"kind": "events", "robot_id": rid, "data": {
                "type": "event", "event": "inspection_complete", "ts": time.time(),
                "data": {"report_id": resp.report_id, "zones": [z.zone for z in rep.zones] if rep else [],
                         "issues": issues, "schedule": sched["name"]}}})
    except Exception as e:  # noqa: BLE001
        log.exception("scheduled patrol %s failed", sched["name"])
        S.store.mark_schedule(sched["id"], status=f"error: {e}")


async def _scheduler():
    """Fires saved patrols at their local time (checked every 20 s)."""
    while True:
        try:
            now = time.localtime()
            hhmm = time.strftime("%H:%M", now)
            key = time.strftime("%Y-%m-%d %H:%M", now)
            for sched in S.store.list_schedules():
                if (sched["enabled"] and sched["time"] == hhmm and now.tm_wday in sched["days"]
                        and sched.get("last_key") != key):
                    S.store.mark_schedule(sched["id"], key=key)
                    log.info("Scheduled patrol: %s -> %s", sched["name"], sched["command"])
                    asyncio.create_task(_run_schedule(sched, key))
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("scheduler tick failed")
        await asyncio.sleep(20)


# ======================================================================= robots
@app.get("/robots")
async def robots(user: dict = Depends(require_role("viewer"))):
    return [r.summary() for r in S.bridge.robots.values()]


@app.get("/robots/{robot_id}")
async def robot_detail(robot_id: str, user: dict = Depends(require_role("viewer"))):
    r = _robot(robot_id)
    return {**r.summary(), "telemetry": r.telemetry, "info": r.info, "events": r.events[-30:]}


@app.post("/robots/{robot_id}/command")
async def robot_command(robot_id: str, body: CommandRequest, user: dict = Depends(require_role("viewer"))):
    _robot(robot_id)
    level = ROLE_LEVEL[user["role"]]
    if body.action in ADMIN_ACTIONS and level < ROLE_LEVEL["admin"]:
        raise HTTPException(403, f"'{body.action}' requires admin")
    if body.action not in VIEWER_ACTIONS and level < ROLE_LEVEL["operator"]:
        raise HTTPException(403, f"'{body.action}' requires operator")
    if body.action != "drive":  # tele-op sends ~5 msgs/s; don't flood the audit log
        S.store.audit(user["sub"], f"command:{body.action}", body.params)
    ack = await S.bridge.send(robot_id, body.action, body.params, issued_by=user["sub"], wait=body.wait)
    return ack.model_dump()


@app.get("/robots/{robot_id}/history")
async def robot_history(robot_id: str, minutes: int = Query(15, ge=1, le=60), user: dict = Depends(require_role("viewer"))):
    r = _robot(robot_id)
    since = time.time() - minutes * 60
    return [h for h in r.history if h["ts"] >= since]


@app.get("/robots/{robot_id}/map")
async def robot_map(robot_id: str, user: dict = Depends(require_role("viewer"))):
    """Zones + floor-plan hints + latest inspection verdict per zone, for the app's mini-map."""
    r = _robot(robot_id)
    info = r.info or {}
    return {"zones": info.get("zones", {}), "map": info.get("map") or {}, "status": S.store.zone_status(),
            "pose": (r.telemetry or {}).get("pose")}


@app.post("/robots/{robot_id}/estop")
async def estop(robot_id: str, user: dict = Depends(require_role("viewer"))):
    """Emergency stop - any logged-in user may press it."""
    S.store.audit(user["sub"], "ESTOP")
    ack = await S.bridge.send(robot_id, "estop", {}, timeout=5, issued_by=user["sub"])
    return ack.model_dump()


@app.post("/robots/{robot_id}/reset")
async def reset(robot_id: str, user: dict = Depends(require_role("operator"))):
    S.store.audit(user["sub"], "reset_estop")
    return (await S.bridge.send(robot_id, "reset", {}, timeout=5, issued_by=user["sub"])).model_dump()


@app.get("/robots/{robot_id}/ping")
async def ping(robot_id: str, user: dict = Depends(require_role("viewer"))):
    samples = [await S.bridge.ping(robot_id) for _ in range(5)]
    ok = sorted(s for s in samples if s is not None)
    return {"samples_ms": samples, "median_ms": ok[len(ok) // 2] if ok else None, "max_ms": ok[-1] if ok else None}


@app.get("/robots/{robot_id}/frame.jpg")
async def frame(robot_id: str, user: dict = Depends(require_role("viewer"))):
    """Latest camera frame as JPEG - video fallback when WebRTC is unavailable (e.g. Expo Go)."""
    _robot(robot_id)
    cached = S.frame_cache.get(robot_id)
    if cached and time.time() - cached[0] < 0.4:
        return Response(cached[1], media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    ack = await S.bridge.send(robot_id, "snapshot", {"size": 640}, timeout=8)
    if ack.status == "rejected":
        raise HTTPException(403, ack.error or "privacy mode")
    if ack.status != "ok":
        raise HTTPException(503, ack.error or ack.status)
    data = base64.b64decode(ack.result["image_b64"])
    S.frame_cache[robot_id] = (time.time(), data)
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/webrtc/offer")
async def webrtc_offer(body: WebRTCOffer, user: dict = Depends(require_role("viewer"))):
    """Signalling: the app sends its SDP offer, the robot (aiortc) answers via MQTT."""
    rid = body.robot_id or settings.robot_id
    S.store.audit(user["sub"], "video_stream_opened", {"robot": rid})
    ack = await S.bridge.send(rid, "webrtc_offer", {"sdp": body.sdp, "type": body.type}, timeout=20)
    if ack.status != "ok":
        raise HTTPException(503 if ack.status != "rejected" else 403, ack.error or ack.status)
    return ack.result


# ======================================================================= agent
@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, user: dict = Depends(require_role("operator"))):
    rid = body.robot_id or settings.robot_id
    S.store.audit(user["sub"], "chat", {"message": body.message})

    async def emit(ev: dict):
        await S.hub.send_user(user["sub"], {"kind": "agent", "robot_id": rid, "data": ev})

    resp = await S.agent.run(body.message, rid, user["sub"], emit, zone_hint=body.zone_hint)
    S.store.save_chat(user["sub"], body.message, resp.reply, resp.report_id)
    if resp.report_id:
        rep = S.store.get_report(resp.report_id)
        issues = sum(len(z.anomalies) for z in rep.zones) if rep else 0
        await S.hub.send_all({"kind": "events", "robot_id": rid, "data": {
            "type": "event", "event": "inspection_complete", "ts": time.time(),
            "data": {"report_id": resp.report_id, "zones": [z.zone for z in rep.zones] if rep else [],
                     "issues": issues}}})
    return resp


@app.get("/chat/history")
async def chat_history(user: dict = Depends(require_role("viewer"))):
    return S.store.list_chat(user["sub"])


# ======================================================================= reports / memory
@app.get("/reports")
async def reports(limit: int = 50, offset: int = 0, zone: str | None = None,
                  user: dict = Depends(require_role("viewer"))):
    return S.store.list_reports(limit, offset, zone)


@app.get("/reports/{report_id}")
async def report(report_id: str, user: dict = Depends(require_role("viewer"))):
    r = S.store.get_report(report_id)
    if not r:
        raise HTTPException(404, "report not found")
    return r.model_dump()


@app.get("/reports/{report_id}/print", response_class=HTMLResponse)
async def report_print(report_id: str, user: dict = Depends(require_role("viewer"))):
    """Printable, self-contained HTML (images inlined) - the app turns it into a PDF."""
    from .report import render_html

    r = S.store.get_report(report_id)
    if not r:
        raise HTTPException(404, "report not found")
    return HTMLResponse(render_html(r, settings.data_dir))


@app.get("/images/{name}")
async def image(name: str, user: dict = Depends(require_role("viewer"))):
    p = (Path(settings.data_dir) / "images" / Path(name).name)
    if not p.exists():
        raise HTTPException(404, "image not found")
    return FileResponse(p, media_type="image/jpeg")


@app.get("/search")
async def search(q: str, zone: str | None = None, days: int | None = None, k: int = Query(5, le=20),
                 user: dict = Depends(require_role("viewer"))):
    if S.memory is None:
        raise HTTPException(503, f"semantic memory not ready: {S.memory_error or 'loading...'}")
    zones = list(((S.bridge.robots.get(settings.robot_id).info or {}).get("zones") or {}).keys()) \
        if settings.robot_id in S.bridge.robots else []
    return await asyncio.to_thread(S.memory.search, q, k, zone, days, True, zones)


@app.post("/memory/seed")
async def seed(n: int = 60, user: dict = Depends(require_role("admin"))):
    if S.memory is None:
        raise HTTPException(503, "semantic memory not ready")
    count = await asyncio.to_thread(S.memory.seed, n)
    S.store.audit(user["sub"], "memory_seed", {"n": n})
    return {"seeded": count, "total": S.memory.count()}


@app.get("/audit")
async def audit(limit: int = 200, user: dict = Depends(require_role("admin"))):
    return S.store.list_audit(limit)


# ======================================================================= websocket
@app.websocket("/ws")
async def ws(websocket: WebSocket, token: str):
    try:
        user = decode_token(token)
    except HTTPException:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    S.hub.clients[websocket] = user
    # send current snapshot immediately
    for rid, r in S.bridge.robots.items():
        if r.telemetry:
            await websocket.send_json({"kind": "telemetry", "robot_id": rid, "data": r.telemetry})
    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") == "ping":
                await websocket.send_json({"kind": "pong", "ts": time.time()})
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        pass
    finally:
        S.hub.clients.pop(websocket, None)


# ======================================================================= pairing page
def _lan_ip() -> str:
    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # no packet is sent; just picks the outgoing interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


@app.get("/brand/logo.svg")
async def brand_logo():
    p = BACKEND_DIR / "app" / "logo.svg"
    return FileResponse(p, media_type="image/svg+xml")


@app.get("/connect", response_class=HTMLResponse)
async def connect_page(port: int = 8000):
    """Open on the PC: shows a QR code the mobile app scans to connect (Login > Scan QR)."""
    url = f"http://{_lan_ip()}:{port}"
    try:
        import segno

        svg = segno.make(url, error="m").svg_inline(scale=8, dark="#14232E", light="#ffffff")
    except Exception:  # noqa: BLE001
        svg = "<p>(install the 'segno' package to show a QR code)</p>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Connect a phone</title>
<style>body{{font-family:system-ui,sans-serif;background:#EEF1EF;color:#14232E;display:grid;place-items:center;
min-height:100vh;margin:0}}main{{background:#fff;padding:32px 40px;border-radius:20px;text-align:center;
box-shadow:0 2px 0 #D5DDD9;max-width:420px}}h1{{font-size:22px;margin:0 0 6px}}p{{color:#4A5A63;line-height:1.5}}
code{{font-size:18px;background:#E3EAE6;padding:4px 10px;border-radius:8px}}</style></head><body><main>
<h1>Connect the Inspection Robot app</h1><p>In the app, tap <b>Scan QR code</b> on the sign-in screen and point it here.</p>
{svg}<p>Or type this server address:</p><code>{url}</code>
<p style="font-size:13px">Phone and PC must be on the same Wi-Fi. If the phone can't connect, allow Python in Windows Firewall.</p>
</main></body></html>"""


# ======================================================================= web app
class _SPAStatic(StaticFiles):
    """Serves the exported Expo web build; unknown paths fall back to index.html (client-side routes)."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:
            if e.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


_WEBAPP = BACKEND_DIR / "webapp"
if (_WEBAPP / "index.html").exists():
    # mounted last, so every API route above takes precedence.  Open http://localhost:8000
    app.mount("/", _SPAStatic(directory=str(_WEBAPP), html=True), name="webapp")
