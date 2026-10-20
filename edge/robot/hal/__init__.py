"""Hardware factory: returns simulated or real hardware based on config."""
from __future__ import annotations

import logging

from .base import Hardware

log = logging.getLogger(__name__)


def _with_harness(hw: Hardware) -> Hardware:
    """Simulated robots get a virtual wiring harness (off until the Wiring Bench turns it on)."""
    from .harness import install_harness

    import os

    if os.environ.get('RAQIB_NO_HARNESS') != '1':
        install_harness(hw)
    return hw


def create_hardware(cfg: dict) -> Hardware:
    if cfg.get("simulator") == "webots":
        from .webots import create_webots_hardware

        log.warning("WEBOTS MODE - the robot in the Webots world is driven by this program")
        return _with_harness(create_webots_hardware(cfg))
    if cfg.get("simulation", True):
        from .sim import create_sim_hardware

        log.warning("SIMULATION MODE - no real motors or sensors are used")
        return _with_harness(create_sim_hardware(cfg))

    board = str(cfg.get("hardware", {}).get("board") or "esp32").lower()
    if board == "esp32":
        from .esp32 import create_esp32_hardware

        log.info("REAL ROBOT MODE - ESP32 over Wi-Fi (this PC is the brain)")
        return create_esp32_hardware(cfg)

    from .real import create_real_hardware

    log.info("REAL HARDWARE MODE - Raspberry Pi")
    return create_real_hardware(cfg)


__all__ = ["create_hardware", "Hardware"]
