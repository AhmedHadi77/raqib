"""Finite state machine: IDLE, MANUAL, AUTONOMOUS_PATROL, EMERGENCY_STOP (+ SAFE_HOLD)."""
from __future__ import annotations

import logging
import threading
from enum import Enum

log = logging.getLogger(__name__)


class State(str, Enum):
    IDLE = "IDLE"
    MANUAL = "MANUAL"
    AUTONOMOUS_PATROL = "AUTONOMOUS_PATROL"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    SAFE_HOLD = "SAFE_HOLD"          # cloud connection lost (T-09)


ALLOWED = {
    State.IDLE: {State.MANUAL, State.AUTONOMOUS_PATROL, State.EMERGENCY_STOP, State.SAFE_HOLD},
    State.MANUAL: {State.IDLE, State.AUTONOMOUS_PATROL, State.EMERGENCY_STOP, State.SAFE_HOLD},
    State.AUTONOMOUS_PATROL: {State.IDLE, State.MANUAL, State.EMERGENCY_STOP, State.SAFE_HOLD},
    State.SAFE_HOLD: {State.IDLE, State.EMERGENCY_STOP},
    State.EMERGENCY_STOP: {State.IDLE},   # only via explicit reset
}


class StateMachine:
    def __init__(self, on_change=None):
        self._state = State.IDLE
        self._lock = threading.Lock()
        self.on_change = on_change or (lambda old, new, reason: None)

    @property
    def state(self) -> State:
        return self._state

    def can_move(self) -> bool:
        return self._state not in (State.EMERGENCY_STOP, State.SAFE_HOLD)

    def transition(self, new: State, reason: str = "") -> bool:
        with self._lock:
            old = self._state
            if new == old:
                return True
            if new not in ALLOWED[old]:
                log.debug("transition %s -> %s refused", old, new)
                return False
            self._state = new
        log.info("STATE %s -> %s (%s)", old.value, new.value, reason)
        self.on_change(old, new, reason)
        return True
