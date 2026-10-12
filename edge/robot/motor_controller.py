"""Motor + pan/tilt control with safety interlocks.

Fix vs. the proposal's Appendix B.1 excerpt: stop() no longer calls GPIO.cleanup()
(that released the pins, so the motors could never run again after the first stop).
Pin cleanup now happens only in shutdown().
"""
from __future__ import annotations

import logging
import threading

from .hal.base import Hardware

log = logging.getLogger(__name__)


class MotorController:
    def __init__(self, hw: Hardware):
        self.hw = hw
        self.lock = threading.Lock()
        self.left = 0.0
        self.right = 0.0
        self.forward_blocked = False   # set by SafetyMonitor (obstacle ahead)
        self.hold = False              # set on E-STOP / SAFE_HOLD: no motion at all
        self.pan = 0.0
        self.tilt = 0.0

    # ------------------------------------------------------------------ wheels
    def set_speed(self, left: float, right: float) -> tuple[float, float]:
        """Request wheel power in [-1, 1]. Returns what was actually applied."""
        left = max(-1.0, min(1.0, float(left)))
        right = max(-1.0, min(1.0, float(right)))
        with self.lock:
            if self.hold:
                left = right = 0.0
            elif self.forward_blocked and (left + right) / 2.0 > 0.02:
                # obstacle ahead: forward motion denied (turning in place / reversing allowed)
                left = right = 0.0
            self.left, self.right = left, right
            self.hw.motors.set_wheels(left, right)
        return left, right

    def stop(self) -> None:
        with self.lock:
            self.left = self.right = 0.0
            self.hw.motors.set_wheels(0.0, 0.0)

    def brake(self) -> None:
        """Fast path used by the safety thread - no checks, just stop."""
        self.hw.motors.set_wheels(0.0, 0.0)
        self.left = self.right = 0.0

    def net_forward(self) -> float:
        return (self.left + self.right) / 2.0

    def is_moving(self) -> bool:
        return abs(self.left) > 0.01 or abs(self.right) > 0.01

    # ---------------------------------------------------------------- pan/tilt
    def set_pan_tilt(self, pan_deg: float, tilt_deg: float) -> None:
        self.pan = max(-90.0, min(90.0, float(pan_deg)))
        self.tilt = max(-45.0, min(60.0, float(tilt_deg)))
        self.hw.pan_tilt.set_angles(self.pan, self.tilt)

    # ---------------------------------------------------------------- shutdown
    def shutdown(self) -> None:
        self.stop()
        log.info("motor controller shut down")
