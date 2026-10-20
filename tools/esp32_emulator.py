"""Pretend to be the ESP32 robot: the same HTTP API as esp32/raqib_esp32, driven by the 2D simulator.

    python tools/esp32_emulator.py                 # control on :8780, audio on :8782
    python -m robot.main --esp32 127.0.0.1:8780 --config ...   (with hardware.esp32_audio_port: 8782)

Used by the tests (the real Wi-Fi driver talks to it) and to try ESP32 mode before the parts arrive.
It copies the firmware's rules: 0.6 s dead-man, no driving forward under stop_cm, soft start.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import sys
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "edge"))

from robot.config import load_config, load_sim_world  # noqa: E402
from robot.hal.sim import SimCamera, SimEnv, SimMicrophone, SimUltrasonics, SimWorld  # noqa: E402


class FakeEsp32:
    def __init__(self, cfg: dict):
        self.w = SimWorld(cfg, load_sim_world(cfg.get("sim_world_path")))
        self.cam = SimCamera(self.w, cfg)
        self.mic = SimMicrophone(self.w)
        self.env = SimEnv(self.w, cfg, voc=False, gas=False)
        self.us = SimUltrasonics(self.w, front_only=True)
        self.settings = {"stop_cm": 15.0, "max_duty": 0.7, "ramp": 4.0, "deadman_ms": 600, "inv_l": False, "inv_r": False}
        self.tgt = [0.0, 0.0]
        self.out = [0.0, 0.0]
        self.last_cmd = 0.0
        self.blocked = False
        self.yaw0 = 0.0
        self.min_power = 0.3
        self.turn = {"active": False, "target": 0.0, "power": 0.5, "deadline": 0.0, "result": "idle"}
        self.yaw_total = 0.0
        self._last_theta = 0.0
        self.dist = 400.0
        self.lock = threading.Lock()
        self.t0 = time.monotonic()
        self._stop = threading.Event()
        threading.Thread(target=self._control, daemon=True).start()

    @staticmethod
    def _step(out: float, target: float, max_up: float) -> float:
        if target == 0.0 or out * target < 0.0:
            out = 0.0
        if abs(target) <= abs(out):
            return target
        return out + math.copysign(min(max_up, abs(target) - abs(out)), target)

    def _control(self):
        while not self._stop.is_set():
            self.dist = self.us.read_cm()["center"]
            with self.w.lock:
                th, gz = self.w.theta, self.w.gyro_z
            self.yaw_total += (math.degrees(th - self._last_theta) + 180) % 360 - 180
            self._last_theta = th
            with self.lock:
                tl, tr = self.tgt
                tn = self.turn
                if tn["active"]:                     # the firmware's own gyro turn
                    err = tn["target"] - self.yaw_total - gz * 0.015
                    if abs(err) < 1.5:
                        tn["active"], tn["result"] = False, "done"
                    elif time.monotonic() > tn["deadline"]:
                        tn["active"], tn["result"] = False, "timeout"
                    else:
                        p = max(self.min_power, min(tn["power"], tn["power"] * abs(err) / 45.0))
                        d = 1.0 if err > 0 else -1.0
                        tl, tr = -d * p, d * p
                        self.last_cmd = time.monotonic()
                    if not tn["active"]:
                        tl = tr = 0.0
                elif (time.monotonic() - self.last_cmd) * 1000 > self.settings["deadman_ms"]:
                    tl = tr = 0.0
                    self.tgt = [0.0, 0.0]
                b = (tl + tr) > 0.05 and self.dist < self.settings["stop_cm"]
                if b:
                    tl = tr = 0.0
                self.blocked = b
                up = self.settings["ramp"] * 0.01
                self.out = [self._step(self.out[0], tl, up), self._step(self.out[1], tr, up)]
                l = -self.out[0] if self.settings["inv_l"] else self.out[0]
                r = -self.out[1] if self.settings["inv_r"] else self.out[1]
            with self.w.lock:
                self.w.cmd_l, self.w.cmd_r = l, r
            time.sleep(0.01)

    def status(self) -> dict:
        with self.w.lock:
            theta, gz = self.w.theta, self.w.gyro_z
        try:
            e = self.env.read()
            t, rh, p = e.temperature_c, e.humidity_pct, e.pressure_hpa
        except Exception:  # noqa: BLE001
            t = rh = p = None
        yaw = (math.degrees(theta) - self.yaw0 + 180) % 360 - 180
        return {"fw": "3.0.0-emulator", "board": "xiao_esp32s3_sense", "ip": "127.0.0.1", "mode": "sta", "ssid": "emulator",
                "up_s": round(time.monotonic() - self.t0, 1), "rssi": -50, "dist_cm": round(self.dist, 1), "us_ok": True,
                "blocked": self.blocked, "turn": self.turn["result"],
                "turn_err": round(self.turn["target"] - self.yaw_total, 1) if self.turn["active"] else 0.0, "yaw": round(yaw, 2), "pitch": 0.0, "roll": 0.0, "gz": round(gz, 2),
                "ax": 0.0, "ay": 0.0, "az": 1.0, "imu_ok": True, "temp_c": t, "rh": rh, "press_hpa": p,
                "aht_ok": t is not None, "bmp_ok": p is not None, "cam_ok": True, "mic_ok": True, "heap_kb": 200,
                "motors": [round(self.out[0], 3), round(self.out[1], 3)], "target": [round(x, 3) for x in self.tgt]}

    def close(self):
        self._stop.set()
        self.w.stop()


def make_handler(dev: FakeEsp32):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj):
            self._send(200, json.dumps(obj).encode(), "application/json")

        def do_GET(self):  # noqa: N802
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            f = lambda k, d=0.0: float(q.get(k, d))  # noqa: E731
            if u.path == "/status":
                return self._json(dev.status())
            if u.path == "/turn":
                with dev.lock:
                    deg = max(-720.0, min(720.0, f("deg")))
                    dev.tgt = [0.0, 0.0]
                    dev.turn = {"active": True, "target": dev.yaw_total + deg, "power": max(0.1, min(1.0, f("power", 0.5))),
                                "deadline": time.monotonic() + abs(deg) / 30.0 + 4.0, "result": "turning"}
                return self._json(dev.status())
            if u.path == "/drive":
                with dev.lock:
                    if dev.turn["active"]:
                        dev.turn.update(active=False, result="stopped")
                    dev.tgt = [max(-1.0, min(1.0, f("l"))), max(-1.0, min(1.0, f("r")))]
                    dev.last_cmd = time.monotonic()
                return self._json(dev.status())
            if u.path == "/stop":
                with dev.lock:
                    if dev.turn["active"]:
                        dev.turn.update(active=False, result="stopped")
                    dev.tgt, dev.out = [0.0, 0.0], [0.0, 0.0]
                return self._json(dev.status())
            if u.path == "/reset_yaw":
                with dev.w.lock:
                    dev.yaw0 = math.degrees(dev.w.theta)
                return self._json(dev.status())
            if u.path == "/config":
                s = dev.settings
                for k in ("stop_cm", "max_duty", "ramp", "deadman_ms"):
                    if k in q:
                        s[k] = float(q[k])
                for k in ("inv_l", "inv_r"):
                    if k in q:
                        s[k] = q[k] not in ("0", "false")
                if "min_power" in q:
                    dev.min_power = float(q["min_power"])
                return self._json(s)
            if u.path == "/capture":
                from PIL import Image

                img = dev.cam.capture()[:, :, ::-1]
                buf = io.BytesIO()
                Image.fromarray(img).save(buf, "JPEG", quality=80)
                return self._send(200, buf.getvalue(), "image/jpeg")
            if u.path == "/audio":
                ms = max(100.0, min(5000.0, f("ms", 1000)))
                x = dev.mic.record(ms / 1000.0, 16000)
                buf = io.BytesIO()
                with wave.open(buf, "wb") as w:
                    w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000), w.writeframes(x.tobytes())
                return self._send(200, buf.getvalue(), "audio/wav")
            self._send(404, b"not found", "text/plain")

    return H


def serve(port: int = 8780, audio_port: int = 8782, config: str | None = None):
    cfg = load_config(config)
    dev = FakeEsp32(cfg)
    h = make_handler(dev)
    servers = [ThreadingHTTPServer(("127.0.0.1", port), h), ThreadingHTTPServer(("127.0.0.1", audio_port), h)]
    for s in servers:
        s.daemon_threads = True
        threading.Thread(target=s.serve_forever, daemon=True).start()
    return dev, servers


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--audio-port", type=int, default=8782)
    ap.add_argument("--config", default=None)
    a = ap.parse_args()
    dev, servers = serve(a.port, a.audio_port, a.config)
    print(f"ESP32 emulator: http://127.0.0.1:{a.port}/status  (audio :{a.audio_port})  Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    for s in servers:
        s.shutdown()
    dev.close()


if __name__ == "__main__":
    main()
