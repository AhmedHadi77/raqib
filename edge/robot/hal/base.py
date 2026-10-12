"""Hardware Abstraction Layer (HAL) interfaces.

Every module in the robot talks to hardware ONLY through these interfaces.
`sim.py` implements them with a physics simulation; `real.py` implements them
with the real Raspberry Pi drivers. Switching `simulation:` in config.yaml swaps
the implementation - nothing else in the code changes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


class Motors(ABC):
    @abstractmethod
    def set_wheels(self, left: float, right: float) -> None:
        """Wheel power in [-1, 1] (negative = reverse)."""

    def stop(self) -> None:
        self.set_wheels(0.0, 0.0)

    def close(self) -> None:
        self.stop()


class PanTilt(ABC):
    @abstractmethod
    def set_angles(self, pan_deg: float, tilt_deg: float) -> None:
        """Pan/tilt in degrees; 0,0 = straight ahead, range about -90..90."""

    def close(self) -> None:
        pass


class Ultrasonics(ABC):
    @abstractmethod
    def read_cm(self) -> dict[str, float]:
        """Latest distances {'left','center','right'} in cm (400 = nothing in range)."""

    def close(self) -> None:
        pass


class Encoders(ABC):
    @abstractmethod
    def ticks(self) -> tuple[int, int]:
        """Cumulative (left, right) tick counts (unsigned - direction from motor command)."""

    def close(self) -> None:
        pass


@dataclass
class ImuReading:
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    gyro_z_dps: float = 0.0
    accel_g: tuple[float, float, float] = (0.0, 0.0, 1.0)


class Imu(ABC):
    @abstractmethod
    def read(self) -> ImuReading: ...

    def close(self) -> None:
        pass


@dataclass
class EnvRaw:
    temperature_c: float
    humidity_pct: float
    pressure_hpa: float
    gas_resistance_ohm: float | None
    mq135_volts: float | None = None


class EnvSensor(ABC):
    @abstractmethod
    def read(self) -> EnvRaw: ...

    def close(self) -> None:
        pass


class Camera(ABC):
    @abstractmethod
    def capture(self) -> np.ndarray:
        """Return a BGR image (H, W, 3) uint8."""

    def scene_truth(self) -> dict | None:
        """Simulation only: ground truth of what the camera sees (used by the mock VLM)."""
        return None

    def close(self) -> None:
        pass


class Microphone(ABC):
    @abstractmethod
    def record(self, seconds: float, sample_rate: int) -> np.ndarray:
        """Return mono int16 samples."""

    def close(self) -> None:
        pass


class Speaker(ABC):
    @abstractmethod
    def say(self, text: str) -> None: ...

    def beep(self, kind: str = "info") -> None:
        pass

    def close(self) -> None:
        pass


@dataclass
class BatteryReading:
    voltage: float | None
    percent: float | None
    charging: bool | None = None


class Battery(ABC):
    @abstractmethod
    def read(self) -> BatteryReading: ...

    def close(self) -> None:
        pass


@dataclass
class Hardware:
    motors: Motors
    pan_tilt: PanTilt
    ultrasonics: Ultrasonics
    encoders: Encoders
    imu: Imu
    env: EnvSensor
    camera: Camera
    microphone: Microphone
    speaker: Speaker
    battery: Battery
    simulated: bool = False
    extra: dict = field(default_factory=dict)
    # component -> {"ok": bool, "detail": str, "hint": str}; filled by the factory, updated at runtime
    health: dict = field(default_factory=dict)

    def set_health(self, part: str, ok: bool, detail: str = "", hint: str = "") -> None:
        prev = self.health.get(part, {})
        self.health[part] = {"ok": ok, "detail": detail or prev.get("detail", ""), "hint": hint or prev.get("hint", "")}

    def faults(self) -> list[str]:
        return sorted(k for k, v in self.health.items() if not v.get("ok"))

    def close(self) -> None:
        for part in (self.motors, self.pan_tilt, self.ultrasonics, self.encoders, self.imu,
                     self.env, self.camera, self.microphone, self.speaker, self.battery):
            try:
                part.close()
            except Exception:  # noqa: BLE001 - best effort shutdown
                pass
