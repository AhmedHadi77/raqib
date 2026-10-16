"""End-to-end test of the WHOLE system in simulation (no hardware, no Docker).

    python tools/e2e_test.py

Starts: backend (with embedded MQTT broker) + simulated robot, then runs the
proposal's test cases that can be automated and prints a KPI table.
Requires the backend and edge Python packages installed in the current Python.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("E2E_PORT", "8010"))
MQTT_PORT = int(os.environ.get("E2E_MQTT_PORT", "1893"))
BASE = f"http://127.0.0.1:{PORT}"


def http(method, path, body=None, token=None, timeout=200):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


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


def main():
    data = tempfile.mkdtemp(prefix="robot-e2e-")
    env = {**os.environ, "EMBEDDED_BROKER": "true", "MQTT_PORT": str(MQTT_PORT), "DATA_DIR": data,
           "EMBEDDING_BACKEND": os.environ.get("EMBEDDING_BACKEND", "auto"), "LLM_PROVIDER": "none",
           "VLM_PROVIDER": "mock", "PYTHONUNBUFFERED": "1"}
    logs = Path(data)
    backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT)],
                               cwd=ROOT / "backend", env=env, stdout=open(logs / "backend.log", "w"),
                               stderr=subprocess.STDOUT)
    robot = None
    results = []
    try:
        wait(lambda: http("GET", "/health")["mqtt_connected"], 40, "backend")
        robot = subprocess.Popen([sys.executable, "-m", "robot.main", "--sim", "--mqtt-port", str(MQTT_PORT)],
                                 cwd=ROOT / "edge", env={**env, "ROBOT_SIMULATION": "true"},
                                 stdout=open(logs / "edge.log", "w"), stderr=subprocess.STDOUT)
        wait(lambda: http("GET", "/health")["robots"]["robot01"]["online"], 40, "robot online")
        tok = http("POST", "/auth/login", {"username": "operator", "password": "operator123"})["access_token"]
        admin = http("POST", "/auth/login", {"username": "admin", "password": "admin123"})["access_token"]

        def check(tid, name, ok, detail=""):
            results.append((tid, name, "PASS" if ok else "FAIL", detail))
            print(f"[{'PASS' if ok else 'FAIL'}] {tid} {name} {detail}")

        # T-09 style communication KPI
        p = http("GET", "/robots/robot01/ping", token=tok)
        check("KPI", "MQTT round-trip < 80 ms", p["median_ms"] is not None and p["median_ms"] < 80, f"{p['median_ms']} ms")

        # T-10 + T-03 + T-04 + T-05 + T-06 + T-07: full conversational inspection
        t0 = time.time()
        r = http("POST", "/chat", {"message": "Inspect the IoT Laboratory and Lecture Hall B"}, tok, timeout=400)
        rep = http("GET", f"/reports/{r['report_id']}", token=tok)
        z = {x["zone"]: x for x in rep["zones"]}
        lab, hb = z.get("IoT_Lab"), z.get("LectureHall_B")
        check("T-10", "conversational inspection produces a report", bool(lab and hb), f"{time.time()-t0:.1f} s total")
        types = {a["type"] for a in lab["anomalies"]} if lab else set()
        check("T-03", "energy waste flagged (lights/projector ON, empty room)",
              "energy_waste" in {a["type"] for a in hb["anomalies"]} if hb else False)
        check("T-04", "blocked emergency exit flagged", "blocked_exit" in types)
        check("T-05", "hot & humid room -> UNCOMFORTABLE", lab and lab["comfort_verdict"] == "UNCOMFORTABLE_HOT_HUMID")
        if lab and lab["gas_verdict"] == "NOT_MEASURED":     # reliable budget build: no gas sensor fitted
            md = str(rep.get("markdown") or "")
            check("T-06", "no gas sensor: report says 'not measured', no false gas alarm",
                  "not measured" in md.lower() and not any(a["type"] == "air_quality" for a in lab["anomalies"]),
                  "markdown has 'not measured'" if "not measured" in md.lower() else f"keys: {list(rep)[:12]}")
        else:
            check("T-06", "VOC source -> gas WARNING", lab and lab["gas_verdict"] in ("WARNING", "HAZARD"))
        check("T-07", "AC audio signature recognised", lab and lab["audio"]["label"] == "ac_fan")

        # V-1..V-3: spoken-style commands get a spoken answer
        r = http("POST", "/chat", {"message": "check the aircon in hall B", "source": "voice"}, tok, timeout=200)
        check("V-1", "\"check the aircon in hall B\" -> over-cooling found and spoken",
              "over-cooled" in r["reply"] and r["speech"] and r["ack"], r["speech"][:70])
        r = http("POST", "/chat", {"message": "what did you find in the lab?"}, tok, timeout=60)
        check("V-2", "\"what did you find\" recalls the last report", "IoT Lab had" in r["reply"] and r["report_id"])
        r = http("POST", "/chat", {"message": "move back 30 cm then turn left"}, tok, timeout=60)
        check("V-3", "relative moves by voice", [s["tool"] for s in r["steps"]] == ["move", "turn"]
              and all(s["status"] == "done" for s in r["steps"]), r["reply"])

        # T-01 obstacle stop while navigating to Hall A (chair in corridor)
        r = http("POST", "/robots/robot01/command", {"action": "go_to_zone", "params": {"zone": "LectureHall_A"}}, tok)
        tel = http("GET", "/robots/robot01", token=tok)["telemetry"]
        lat = tel["safety"]["last_stop_latency_ms"]
        check("T-01", "obstacle stop < 50 ms, then avoided", r["status"] == "ok" and lat is not None and lat < 50,
              f"latency {lat} ms, avoidance attempts {r['result'].get('avoidance_attempts')}")

        r = http("POST", "/chat", {"message": "turn around, go forward 1 meter and tell me what you see"}, tok, timeout=120)
        check("V-4", "chained order: turn, move, describe", [s["tool"] for s in r["steps"]] == ["turn", "move", "capture_and_analyze"]
              and "I see" in r["reply"], r["speech"][:70])

        # V-5 / V-6: exam hall - find the person talking, then a monitoring session
        http("POST", "/chat", {"message": "go to the exam hall"}, tok, timeout=200)
        found = None
        for _ in range(12):
            r = http("POST", "/chat", {"message": "who is talking? tell them to stop talking"}, tok, timeout=200)
            if "quiet here" not in r["reply"]:
                found = r
                break
            time.sleep(4)
        check("V-5", "finds the person talking and asks them to stop", bool(found) and "asked them to stop" in found["reply"],
              (found or {}).get("speech", "nobody talked")[:70])
        r = http("POST", "/chat", {"message": "monitor the exam in the exam hall for 5 minutes"}, tok, timeout=60)
        busy = http("POST", "/chat", {"message": "go to hall A"}, tok, timeout=60)
        st = http("GET", "/monitor", token=tok)
        stop = http("POST", "/chat", {"message": "stop monitoring"}, tok, timeout=60)
        check("V-6", "exam monitoring starts, blocks other trips, stops", st["active"] and "monitoring the exam" in busy["reply"]
              and "stopped" in stop["reply"].lower() and not http("GET", "/monitor", token=tok)["active"])

        # V-7: proctoring patrol - sees cheating, warns the student, sends a photo, prints a report
        http("POST", "/monitor/start", {"zone": "Exam_Hall", "minutes": 10, "mode": "patrol"}, tok, timeout=60)
        t0, hit = time.time(), None
        while time.time() - t0 < 240 and not hit:
            time.sleep(5)
            st = http("GET", "/monitor", token=tok)
            hit = next((i for i in st["incidents"] if i["type"] in ("phone", "notes", "earpiece", "head_turn", "looking_down")), None)
        http("POST", "/monitor/stop", token=tok, timeout=60)
        sid = http("GET", "/monitor/sessions", token=tok)[0]["id"]
        req = urllib.request.Request(f"{BASE}/monitor/sessions/{sid}/print", headers={"Authorization": f"Bearer {tok}"})
        html = urllib.request.urlopen(req, timeout=30).read().decode()
        check("V-7", "proctor patrol flags cheating with photo + warning, PDF report",
              bool(hit) and hit["warned"] and bool(hit["image"]) and "exam monitoring report" in html,
              f"{hit['title']} after {time.time() - t0:.0f} s, {st['views']} views" if hit else "nothing flagged")

        # T-08 semantic search
        http("POST", "/memory/seed?n=60", token=admin)
        t0 = time.time()
        s = http("GET", "/search?q=rooms%20where%20the%20air%20quality%20was%20unhealthy%20last%20month", token=tok)
        check("T-08", "semantic search returns records < 2 s", bool(s["results"]) and time.time() - t0 < 2,
              f"{(time.time()-t0)*1000:.0f} ms, {len(s['results'])} hits, embedding={s['embedding']}")

        # E-STOP latch
        http("POST", "/robots/robot01/estop", token=tok)
        r = http("POST", "/robots/robot01/command", {"action": "move", "params": {"distance_m": 0.3}}, tok)
        check("SAFE", "E-STOP blocks motion until reset", r["status"] == "rejected")
        http("POST", "/robots/robot01/reset", token=tok)

        # T-09: cloud loss -> SAFE HOLD after 10 s
        backend.terminate()
        backend.wait(10)
        time.sleep(12.5)
        log = (logs / "edge.log").read_text()
        check("T-09", "cloud lost -> SAFE HOLD after 10 s", "SAFE HOLD" in log or "SAFE_HOLD" in log)
    finally:
        for p in (robot, backend):
            if p and p.poll() is None:
                p.terminate()
        print(f"\nLogs: {logs}")
    failed = [r for r in results if r[2] == "FAIL"]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
