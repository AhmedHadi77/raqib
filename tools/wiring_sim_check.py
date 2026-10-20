"""Wiring + driving check on the simulated ESP32 robot (no hardware needed).

    python tools/wiring_sim_check.py

Starts the server and the simulated robot, places the build guide's wiring on the Wiring Bench (the same wires
as the Cirkit Designer guide), drives the robot (move, turn, joystick, obstacle stop) and reads every sensor.
Then it tries 13 common wiring mistakes and checks that each one is caught with the right fix.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT, MQTT = 8123, 18830
PY = sys.executable
TOK = None


def http(method, path, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {TOK}"} if TOK else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode()[:400]}


def wait(cond, t, what):
    t0 = time.time()
    while time.time() - t0 < t:
        try:
            if cond():
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise SystemExit("timeout: " + what)


GOOD = {
    "pbank.usb": "usbc",
    "drv.vm": "bat+", "drv.gndbat": "bat-", "drv.gndx": "pin:4", "drv.eep": "pin:6",
    "drv.ain1": "pin:1", "drv.ain2": "pin:3", "drv.bin1": "pin:5", "drv.bin2": "pin:7",
    "motors.left": "aout", "motors.right": "bout",
    "us.vcc": "pin:6", "us.gnd": "pin:4", "us.trig": "pin:13", "us.echo": "pin:14",
    "imu.vcc": "pin:6", "imu.gnd": "pin:4", "imu.sda": "pin:9", "imu.scl": "pin:11",
    "aht.vcc": "pin:6", "aht.gnd": "pin:4", "aht.sda": "pin:9", "aht.scl": "pin:11",
    "sense.b2b": "b2b", "sense.cam": "camsock",
}
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((ok, name, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}", flush=True)


def cmd(action, **params):
    return http("POST", "/robots/robot01/command", {"action": action, "params": params}, timeout=120)


def tel():
    time.sleep(1.3)   # the robot publishes telemetry about once a second
    return http("GET", "/robots/robot01")["telemetry"]


def wrap(a):
    return (a + 180) % 360 - 180


def wire(w):
    r = http("PUT", "/wiring", {"enabled": True, "wires": w})
    time.sleep(1.5)
    return r["robot"] or {}


def bad_health(st):
    return {k: v["detail"] for k, v in st["health"].items() if not v["ok"]}


def drive_for(l, r, secs):
    x0 = tel()["pose"]
    t0 = time.time()
    while time.time() - t0 < secs:
        cmd("drive", left=l, right=r)
        time.sleep(0.2)
    cmd("stop")
    time.sleep(0.6)
    x1 = tel()["pose"]
    return x1["x"] - x0["x"], wrap(x1["heading_deg"] - x0["heading_deg"]), x1


def main():
    global TOK
    data = tempfile.mkdtemp(prefix="raqib-sim-")
    env = {**os.environ, "EMBEDDED_BROKER": "true", "MQTT_PORT": str(MQTT), "DATA_DIR": data, "LLM_PROVIDER": "none",
           "VLM_PROVIDER": "mock", "PYTHONUNBUFFERED": "1"}
    be = subprocess.Popen([PY, "-m", "uvicorn", "app.main:app", "--port", str(PORT)], cwd=ROOT / "backend", env=env,
                          stdout=open(Path(data) / "backend.log", "w"), stderr=subprocess.STDOUT)
    rb = None
    try:
        wait(lambda: http("GET", "/health")["mqtt_connected"], 60, "backend")
        rb = subprocess.Popen([PY, "-m", "robot.main", "--sim", "--mqtt-port", str(MQTT)], cwd=ROOT / "edge",
                              env={**env, "ROBOT_SIMULATION": "true"}, stdout=open(Path(data) / "edge.log", "w"),
                              stderr=subprocess.STDOUT)
        wait(lambda: http("GET", "/health")["robots"]["robot01"]["online"], 60, "robot")
        TOK = http("POST", "/auth/login", {"username": "operator", "password": "operator123"})["access_token"]
        spec = http("GET", "/wiring/spec")
        n = sum(len(p["pins"]) for p in spec["parts"])
        check("bench spec loads", n == len(GOOD), f"{n} connections, test wiring has {len(GOOD)}")

        # ------------------------------------------------ 1. the guide's wiring
        st = wire(GOOD)
        check("correct wiring: every wire accepted", st.get("done") == st.get("total"), f"{st.get('done')}/{st.get('total')}")
        check("correct wiring: Ready to drive", st.get("drivable") is True)
        check("correct wiring: all parts green", not bad_health(st), json.dumps(bad_health(st)))
        check("correct wiring: no warnings/shorts", not st.get("warnings") and not st.get("shorts"))

        cmd("reset")
        r = cmd("move", distance_m=1.0)
        p = tel()["pose"]
        check("move forward 1 m", r.get("status") == "ok" and abs(p["x"] - 1.0) < 0.1, f"x = {p['x']:.2f} m  ({r.get('status')})")
        r = cmd("turn", angle_deg=90)
        h = tel()["pose"]["heading_deg"]
        check("turn left 90", r.get("status") == "ok" and abs(h - 90) < 6, f"heading {h:.1f}")
        cmd("turn", angle_deg=-90)
        h = tel()["pose"]["heading_deg"]
        check("turn right back to 0", abs(wrap(h)) < 6, f"heading {h:.1f}")
        dx, dh, _ = drive_for(0.5, 0.5, 1.5)
        check("manual drive forward (joystick)", dx > 0.1 and abs(dh) < 8, f"dx {dx:+.2f} m, turn {dh:+.1f}")
        dx, dh, _ = drive_for(-0.5, -0.5, 1.0)
        check("manual drive backward", dx < -0.05, f"dx {dx:+.2f} m")
        dx, dh, _ = drive_for(-0.5, 0.5, 0.6)
        check("spin left (left wheel back, right forward)", dh > 20, f"turned {dh:+.1f}")
        cmd("turn", angle_deg=-wrap(tel()["pose"]["heading_deg"]))
        env_r = cmd("read_environment", fresh=True)
        res = env_r.get("result", env_r)
        check("climate sensor reads", isinstance(res, dict) and res.get("temperature_c") is not None,
              json.dumps({k: res.get(k) for k in ("temperature_c", "humidity_pct", "pressure_hpa")}) if isinstance(res, dict) else str(res)[:200])
        snap = cmd("snapshot")
        check("camera photo", snap.get("status") == "ok", str(snap.get("status")))
        aud = cmd("listen_audio", seconds=1.0)
        check("microphone listen", aud.get("status") == "ok", str(aud.get("result", aud))[:120])
        # obstacle: the chair at x = 7.3 m, straight ahead
        cmd("set_home")
        cur = tel()["pose"]
        r = cmd("move", distance_m=8.0)
        p = tel()["pose"]
        d = tel().get("ultrasonic_cm", {}).get("center")
        check("stops before the chair (obstacle 15 cm rule)", r.get("status") != "ok" and p["x"] < 7.3 - 0.05,
              f"status {r.get('status')}, stopped at x = {p['x']:.2f} m (chair at 7.30), sonar {d} cm")
        blk = cmd("drive", left=0.5, right=0.5)
        res = blk.get("result", {})
        check("forward refused while blocked, reverse allowed", bool(res.get("blocked")) or res.get("applied", {}).get("left", 1) == 0,
              json.dumps(res)[:160])
        drive_for(-0.5, -0.5, 1.0)

        # ------------------------------------------------ 2. the classic mistakes
        def case(name, change, expect_key, expect_txt, drivable=False, motion=None):
            w = {**GOOD, **change}
            w = {k: v for k, v in w.items() if v}
            st = wire(w)
            bad = bad_health(st) | ({"shorts": "; ".join(st.get("shorts") or [])} if st.get("shorts") else {}) | \
                ({"warnings": "; ".join(st.get("warnings") or [])} if st.get("warnings") else {})
            msg = " | ".join(f"{k}: {v}" for k, v in bad.items())
            ok = st.get("drivable") == drivable and any(expect_txt.lower() in str(v).lower() for v in bad.values())
            extra = ""
            if motion and ok:
                dx, dh, _ = drive_for(0.5, 0.5, 1.2)
                ok = motion(dx, dh)
                extra = f"  [drive fwd: dx {dx:+.2f} m, turn {dh:+.1f}]"
            check(f"mistake: {name}", ok, (msg or "(no message)")[:260] + extra)

        case("no power bank cable", {"pbank.usb": None}, "power", "no power")
        case("DRV8833 GND not on the GND rail", {"drv.gndx": None}, "motors", "ground")
        case("EEP left open", {"drv.eep": None}, "motors", "asleep")
        case("motor battery reversed", {"drv.vm": "bat-", "drv.gndbat": "bat+"}, "motors", "")
        case("motor battery + on the XIAO 5V", {"drv.vm": "pin:2"}, "power", "destroy")
        case("left motor wires reversed (AIN1/AIN2 swapped)", {"drv.ain1": "pin:3", "drv.ain2": "pin:1"}, "motors", "backwards",
             motion=lambda dx, dh: abs(dh) > 20)
        case("left and right motors swapped", {"motors.left": "bout", "motors.right": "aout"}, "motors", "signals")
        case("MPU6050 SDA/SCL swapped", {"imu.sda": "pin:11", "imu.scl": "pin:9"}, "imu", "swapped")
        case("climate board not on I2C", {"aht.sda": None, "aht.scl": None}, "environment", "not on the i2c bus", drivable=True)
        case("sonar TRIG/ECHO swapped", {"us.trig": "pin:14", "us.echo": "pin:13"}, "ultrasonic", "no reading")
        case("sonar VCC on 5V", {"us.vcc": "pin:2"}, "wiring", "5 v")
        case("sensor VCC on GND (short)", {"imu.vcc": "pin:4"}, "power", "short")
        case("camera ribbon out", {"sense.cam": None}, "camera", "camera not connected", drivable=True)

        st = wire(GOOD)
        check("back to correct wiring: Ready to drive again", st.get("drivable") is True and not bad_health(st))
    finally:
        for p in (rb, be):
            if p:
                p.terminate()
        time.sleep(1)
        print("logs:", data)
        fails = [r for r in RESULTS if not r[0]]
        print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} passed")
        if fails:
            sys.exit(1)


if __name__ == "__main__":
    main()
