"""Record real answers from the simulated robot for the phone app's built-in demo mode.

    python tools/make_demo_data.py

Starts the backend + 2D simulated robot (like tools/e2e_test.py), drives through every room, runs real
inspections and an exam-monitoring session, and saves what the server answered to
mobile/src/demo/demoData.json and the camera pictures to mobile/src/demo/demoImages.ts.
The app replays these in demo mode, so the demo shows real robot output, not invented numbers.
"""
from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PORT, MQTT_PORT = 8031, 1903
BASE = f"http://127.0.0.1:{PORT}"
OUT = ROOT / "mobile" / "src" / "demo"


def http(method, path, body=None, token=None, timeout=300, raw=False):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return data if raw else json.loads(data)


def wait(cond, timeout, what):
    t = time.time()
    while time.time() - t < timeout:
        try:
            if cond():
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
    raise SystemExit(f"timeout waiting for {what}")


def small_jpeg(data: bytes, width=480, q=58) -> str:
    im = Image.open(io.BytesIO(data)).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=q, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    data_dir = tempfile.mkdtemp(prefix="raqib-demo-")
    env = {**os.environ, "EMBEDDED_BROKER": "true", "MQTT_PORT": str(MQTT_PORT), "DATA_DIR": data_dir,
           "EMBEDDING_BACKEND": "hash", "LLM_PROVIDER": "none", "VLM_PROVIDER": "mock", "PYTHONUNBUFFERED": "1",
           "DISCOVERY_BEACON": "false", "SITE_NAME": "Demo Campus"}
    backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT)],
                               cwd=ROOT / "backend", env=env, stdout=open(Path(data_dir) / "backend.log", "w"),
                               stderr=subprocess.STDOUT)
    robot = None
    out: dict = {"made": time.time()}
    images: dict[str, str] = {}
    try:
        wait(lambda: http("GET", "/health")["mqtt_connected"], 40, "backend")
        robot = subprocess.Popen([sys.executable, "-m", "robot.main", "--sim", "--mqtt-port", str(MQTT_PORT)],
                                 cwd=ROOT / "edge", env={**env, "ROBOT_SIMULATION": "true"},
                                 stdout=open(Path(data_dir) / "edge.log", "w"), stderr=subprocess.STDOUT)
        wait(lambda: http("GET", "/health")["robots"]["robot01"]["online"], 40, "robot online")
        time.sleep(2)
        tok = http("POST", "/auth/login", {"username": "admin", "password": "admin123"})["access_token"]
        R = "/robots/robot01"

        out["health"] = http("GET", "/health")
        out["robot"] = http("GET", R, token=tok)
        out["map"] = http("GET", f"{R}/map", token=tok)
        out["users"] = http("GET", "/users", token=tok)
        out["ai"] = http("GET", "/admin/ai", token=tok)
        out["caps"] = http("GET", "/monitor/capabilities", token=tok)
        zones = list(out["robot"]["info"]["zones"].keys())
        print("zones", zones)

        # every room: drive there, record telemetry, a fresh environment reading and two camera views
        out["rooms"] = {}
        for z in zones:
            print("room", z)
            http("POST", f"{R}/command", {"action": "go_to_zone", "params": {"zone": z}}, tok, timeout=200)
            env_r = http("POST", f"{R}/command", {"action": "read_environment", "params": {"fresh": True}}, tok)
            tel = http("GET", R, token=tok)["telemetry"]
            frames = []
            for pan in (0, 35):
                http("POST", f"{R}/command", {"action": "pan_tilt", "params": {"pan": pan, "tilt": 0}}, tok)
                time.sleep(0.6)
                key = f"frame_{z}_{pan}"
                images[key] = small_jpeg(http("GET", f"{R}/frame.jpg?x={time.time()}", token=tok, raw=True))
                frames.append(key)
            http("POST", f"{R}/command", {"action": "pan_tilt", "params": {"pan": 0, "tilt": 0}}, tok)
            out["rooms"][z] = {"telemetry": tel, "environment": env_r.get("result"), "frames": frames}

        # real conversations with the agent
        chats = {}
        for key, msg in [("inspect_lab_hallb", "Inspect the IoT Laboratory and Lecture Hall B"),
                         ("inspect_halla", "Inspect Lecture Hall A"),
                         ("inspect_exam", "Inspect the exam hall"),
                         ("aircon_hallb", "check the aircon in hall B"),
                         ("what_found", "what did you find in the lab?"),
                         ("describe", "turn around, go forward 1 meter and tell me what you see")]:
            print("chat", msg)
            chats[key] = {"message": msg, "response": http("POST", "/chat", {"message": msg}, tok, timeout=400)}
        out["chats"] = chats

        out["reports"] = {}
        for item in http("GET", "/reports", token=tok):
            rep = http("GET", f"/reports/{item['id']}", token=tok)
            for zi in rep["zones"]:
                if zi.get("image_file") and zi["image_file"] not in images:
                    images[zi["image_file"]] = small_jpeg(http("GET", f"/images/{zi['image_file']}", token=tok, raw=True))
            out["reports"][item["id"]] = {"item": item, "report": rep}

        # a short exam-monitoring session (patrol) with its incidents and photos
        print("exam monitoring (about 2 minutes)")
        http("POST", "/monitor/start", {"zone": "Exam_Hall", "minutes": 2, "sensitivity": "normal", "mode": "patrol"}, tok, timeout=60)
        out["monitor_live"] = []
        t_end = time.time() + 130
        while time.time() < t_end:
            st = http("GET", "/monitor", token=tok)
            out["monitor_live"].append(st)
            if not st.get("active"):
                break
            time.sleep(10)
        sessions = http("GET", "/monitor/sessions", token=tok)
        out["sessions"] = []
        for s in sessions[:1]:
            full = http("GET", f"/monitor/sessions/{s['id']}", token=tok)
            for inc in full.get("incidents") or []:
                for k in ("image", "close_image"):
                    if inc.get(k) and inc[k] not in images:
                        images[inc[k]] = small_jpeg(http("GET", f"/images/{inc[k]}", token=tok, raw=True))
            out["sessions"].append(full)

        http("POST", "/memory/seed?n=60", token=tok, timeout=120)
        out["search"] = {q: http("GET", f"/search?q={urllib.request.quote(q)}&k=10", token=tok)
                         for q in ("over-cooled rooms", "air quality warning", "blocked exit", "lights left on")}
        out["history"] = http("GET", f"{R}/history?minutes=15", token=tok)
    finally:
        for p in (robot, backend):
            if p:
                p.terminate()
                try:
                    p.wait(10)
                except Exception:  # noqa: BLE001
                    p.kill()

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "demoData.json").write_text(json.dumps(out, separators=(",", ":"), default=str))
    lines = ["// Camera pictures recorded from the simulated robot (tools/make_demo_data.py). Do not edit.",
             "export const DEMO_IMAGES: Record<string, string> = {"]
    for k, v in images.items():
        lines.append(f"  {json.dumps(k)}: {json.dumps(v)},")
    lines.append("};\n")
    (OUT / "demoImages.ts").write_text("\n".join(lines))
    print("saved", len(images), "images,", round((OUT / 'demoImages.ts').stat().st_size / 1e6, 2), "MB;",
          "data", round((OUT / 'demoData.json').stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
