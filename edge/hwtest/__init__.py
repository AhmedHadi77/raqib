"""Hardware bring-up tests:  python -m hwtest.<name>
ESP32 robot: run them on the PC (the robot must be on the same Wi-Fi). Raspberry Pi build: run them on the Pi."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def real_cfg():
    from robot.config import load_config

    return load_config(overrides={"simulation": False})
