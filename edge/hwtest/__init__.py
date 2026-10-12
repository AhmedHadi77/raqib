"""Hardware bring-up tests. Run each on the Pi:  python -m hwtest.<name>"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def real_cfg():
    from robot.config import load_config

    return load_config(overrides={"simulation": False})
