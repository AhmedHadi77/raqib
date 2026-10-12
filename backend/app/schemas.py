"""Contract-first message schemas (Pydantic). The mobile app mirrors these in mobile/src/types.ts."""
from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1


# ----------------------------------------------------------------- MQTT messages
class Command(BaseModel):
    v: int = SCHEMA_VERSION
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    issued_by: str | None = None
    ts: float = Field(default_factory=time.time)


class Ack(BaseModel):
    model_config = ConfigDict(extra="allow")
    v: int = SCHEMA_VERSION
    id: str
    action: str | None = None
    status: Literal["ok", "error", "blocked", "rejected", "timeout", "cancelled"] = "ok"
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class Telemetry(BaseModel):
    """Loose model: the edge may add fields over time (versioned by `v`)."""
    model_config = ConfigDict(extra="allow")
    v: int = SCHEMA_VERSION
    robot_id: str
    ts: float
    state: str
    simulation: bool = False
    privacy_mode: bool = False
    battery: dict[str, Any] = {}
    pose: dict[str, Any] = {}
    ultrasonic_cm: dict[str, float] = {}
    environment: dict[str, Any] | None = None
    audio: dict[str, Any] | None = None
    safety: dict[str, Any] = {}


# ----------------------------------------------------------------- AI results
class Anomaly(BaseModel):
    type: str                                  # energy_waste | blocked_exit | lab_hazard | comfort | air_quality | equipment | other
    description: str
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    source: str = "vlm"                        # vlm | environment | audio | fusion


class VisionAnalysis(BaseModel):
    """Structured output the VLM must return (validated; invalid JSON => fallback)."""
    occupants: int = Field(0, ge=0, description="number of people visible")
    lights_on: bool = False
    projector_on: bool = False
    monitors_on: bool = False
    hazardous_items: list[str] = Field(default_factory=list, description="e.g. soldering iron left on")
    exit_visible: bool = True
    exit_clear: bool = True
    extinguisher_present: bool = False
    water_leak_or_stain: bool = False
    objects: list[str] = Field(default_factory=list, description="main things visible, most prominent first")
    answer: str = Field("", description="first-person spoken answer to the operator's question, starting 'I see'")
    description: str = ""
    confidence: float = Field(0.5, ge=0, le=1)
    provider: str = "unknown"
    needs_human_review: bool = False


class ZoneInspection(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    zone: str
    ts: float = Field(default_factory=time.time)
    vision: VisionAnalysis | None = None
    environment: dict[str, Any] | None = None
    audio: dict[str, Any] | None = None
    image_file: str | None = None
    anomalies: list[Anomaly] = Field(default_factory=list)
    recommended_actions: list[dict[str, str]] = Field(default_factory=list)
    energy_status: str = "unknown"             # OK | WASTE
    safety_status: str = "unknown"             # COMPLIANT | HAZARD
    comfort_verdict: str | None = None
    gas_verdict: str | None = None
    compliant: bool = False
    summary: str = ""


class InspectionReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    created: float = Field(default_factory=time.time)
    robot_id: str
    request: str
    requested_by: str | None = None
    zones: list[ZoneInspection] = Field(default_factory=list)
    title: str = "GREEN CAMPUS ENERGY, INDOOR COMFORT & LAB SAFETY AUDIT REPORT"
    markdown: str = ""
    duration_s: float | None = None


# ----------------------------------------------------------------- REST
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    expires_in: int
    name: str | None = None


Role = Literal["admin", "operator", "viewer"]


class UserIn(BaseModel):
    username: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_.@-]+$")
    password: str = Field(min_length=6, max_length=200)
    role: Role = "operator"
    name: str | None = None


class UserPatch(BaseModel):
    role: Role | None = None
    name: str | None = None
    password: str | None = Field(default=None, min_length=6, max_length=200)
    disabled: bool | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=200)


class ScheduleIn(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=80)
    command: str = Field(min_length=3, max_length=500)
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    days: list[int] = Field(default_factory=lambda: list(range(7)))   # 0 = Monday
    enabled: bool = True
    robot_id: str | None = None


class CommandRequest(BaseModel):
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    wait: bool = True


class ChatRequest(BaseModel):
    message: str
    robot_id: str | None = None
    session_id: str | None = None
    zone_hint: str | None = None      # room selected in the app ("go there")
    source: str = "text"              # text | voice


class AgentStep(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    summary: str = ""
    started: float | None = None
    finished: float | None = None


class ChatResponse(BaseModel):
    reply: str
    steps: list[AgentStep] = Field(default_factory=list)
    report_id: str | None = None
    planner: str = "rules"
    duration_s: float = 0.0
    speech: str = ""                  # plain sentence(s) for text-to-speech
    ack: str | None = None            # spoken acknowledgement sent when the plan was ready
    images: list[str] = Field(default_factory=list)


class WebRTCOffer(BaseModel):
    sdp: str
    type: str = "offer"
    robot_id: str | None = None
