"""Entry point:  python -m robot.main [--sim | --esp32 [HOST] | --real] [--config config.yaml] [--mqtt-host HOST]"""
from __future__ import annotations

import argparse
import logging
import signal
import threading

from .app import RobotApp
from .config import load_config


def main():
    ap = argparse.ArgumentParser(description="AI Agent Inspection Robot - edge controller")
    ap.add_argument("--config", default=None, help="path to config.yaml")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--sim", action="store_true", help="force simulation mode")
    g.add_argument("--esp32", nargs="?", const="auto", default=None, metavar="HOST",
                   help="drive the ESP32 robot over Wi-Fi (address optional: found automatically)")
    g.add_argument("--real", action="store_true", help="real hardware: the board in config.yaml (esp32 or pi)")
    g.add_argument("--webots", action="store_true", help="drive the 3D robot in Webots (open webots/worlds/raqib_campus.wbt first)")
    ap.add_argument("--mqtt-host", default=None)
    ap.add_argument("--mqtt-port", type=int, default=None)
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(level=args.log_level.upper(),
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    overrides: dict = {}
    if args.sim:
        overrides["simulation"] = True
    if args.real:
        overrides["simulation"] = False
    if args.esp32:
        overrides["simulation"] = False
        overrides["hardware"] = {"board": "esp32", **({"esp32_host": args.esp32} if args.esp32 != "auto" else {})}
    if args.webots:
        overrides["simulation"] = True
        overrides["simulator"] = "webots"
    if args.mqtt_host or args.mqtt_port:
        overrides["mqtt"] = {}
        if args.mqtt_host:
            overrides["mqtt"]["host"] = args.mqtt_host
        if args.mqtt_port:
            overrides["mqtt"]["port"] = args.mqtt_port
    cfg = load_config(args.config, overrides)

    app = RobotApp(cfg)
    done = threading.Event()

    def _sig(*_):
        done.set()

    signal.signal(signal.SIGINT, _sig)
    try:
        signal.signal(signal.SIGTERM, _sig)
    except (AttributeError, ValueError):
        pass

    app.start()
    try:
        while not done.wait(0.5):
            pass
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()
