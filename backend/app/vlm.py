"""Vision-Language Model scene analysis (GPT-4o / Gemini Flash / Ollama / mock).

The VLM must answer with structured JSON matching `VisionAnalysis`; the result is
validated with Pydantic and grounded against sensor data (risk R3). If the VLM fails
or returns invalid JSON we fall back to a simple rule-based image check and flag the
result for human review.
"""
from __future__ import annotations

import asyncio
import re
import base64
import logging

import httpx
from langchain_core.messages import HumanMessage, SystemMessage

from .agent.llm import extract_json, get_chat_model, message_text
from .config import Settings
from .schemas import VisionAnalysis

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the vision module of an autonomous facility-inspection robot on a university campus
(Green Campus energy audit, indoor comfort and laboratory safety). You receive ONE camera snapshot of a room.
Answer ONLY with a JSON object with exactly these keys:
{
  "occupants": <int, number of people visible>,
  "lights_on": <bool, ceiling/room lights switched on>,
  "projector_on": <bool, projector or projection screen showing an image>,
  "monitors_on": <bool, computer monitors / lab equipment displays on>,
  "hazardous_items": [<short strings, e.g. "soldering iron left on bench", "open chemical bottle">],
  "exit_visible": <bool, an emergency exit door/sign is visible>,
  "exit_clear": <bool, the exit path is NOT obstructed (true if no exit visible)>,
  "extinguisher_present": <bool, a fire extinguisher is visible>,
  "water_leak_or_stain": <bool>,
  "objects": [<the main things visible, most prominent first, e.g. "whiteboard", "two students at desks">],
  "answer": <a short first-person spoken answer to the operator's question, starting with "I see", 1-2 sentences>,
  "description": <one or two sentences describing the scene>,
  "confidence": <float 0..1, your overall confidence>
}
Be conservative: if you cannot see something clearly, say so in the description and lower the confidence.
Never invent people or equipment that are not visible."""


def _user_prompt(focus: str | None) -> str:
    p = ("Analyse this snapshot. Check (1) human occupancy, (2) unattended ceiling lights, projectors or lab "
         "monitors, (3) hazardous tools left on lab benches, (4) clear emergency exit and fire extinguisher presence.")
    if focus:
        p += f" The operator specifically asked: {focus}"
    return p


def _mock_from_truth(truth: dict | None) -> VisionAnalysis:
    """Simulation 'VLM': reads the simulator's ground truth so the whole pipeline is testable for free."""
    if not truth:
        return VisionAnalysis(description="No VLM configured (VLM_PROVIDER=mock) and no simulator ground truth.",
                              confidence=0.0, provider="mock", needs_human_review=True)
    parts = []
    occ = int(truth.get("occupants", 0))
    parts.append(f"{occ} occupant(s) visible" if occ else "the room appears vacant")
    zone = str(truth.get("zone") or "the corridor").replace("_", " ")
    zone = re.sub(r"([a-z])([A-Z][a-z])", r"\1 \2", zone)
    seen = []
    if occ:
        seen.append("one person" if occ == 1 else f"{occ} people" + (" sitting at desks" if truth.get("talking") is not None else ""))
    if truth.get("lights_on"):
        seen.append("the ceiling lights on")
    if truth.get("projector_on"):
        seen.append("the projector showing a slide")
    if truth.get("monitors_on"):
        seen.append("computer monitors switched on")
    if truth.get("hazardous_tools"):
        seen.append(", ".join(truth["hazardous_tools"]))
    if truth.get("exit_blocked"):
        seen.append("a chair blocking the emergency exit")
    elif truth.get("extinguisher_present"):
        seen.append("the exit door and a fire extinguisher")
    where = "the corridor" if zone.lower() == "corridor" else zone
    if seen:
        answer = f"I see {', '.join(seen[:-1]) + ' and ' + seen[-1] if len(seen) > 1 else seen[0]} in {where}."
    else:
        answer = f"I see {where}, with the lights off."
    if not occ:
        answer += " Nobody is there."
    if truth.get("ahead_m") is not None:
        answer += f" About {truth['ahead_m']:.1f} m straight ahead there is a {truth.get('ahead_object', 'wall')}."
    objects = [truth.get("ahead_object")] if truth.get("ahead_object") else []
    if truth.get("lights_on"):
        parts.append("ceiling lights are on")
    if truth.get("projector_on"):
        parts.append("the projector is displaying a slide")
    if truth.get("monitors_on"):
        parts.append("bench monitors are powered on")
    if truth.get("exit_blocked"):
        parts.append("a chair obstructs the emergency exit")
    return VisionAnalysis(
        occupants=occ,
        lights_on=bool(truth.get("lights_on")),
        projector_on=bool(truth.get("projector_on")),
        monitors_on=bool(truth.get("monitors_on")),
        hazardous_items=list(truth.get("hazardous_tools") or []),
        exit_visible=True,
        exit_clear=not truth.get("exit_blocked", False),
        extinguisher_present=bool(truth.get("extinguisher_present")),
        description=f"[simulated VLM] In {truth.get('zone', 'the room')}: " + ", ".join(parts) + ".",
        answer=answer,
        objects=objects,
        confidence=0.95,
        provider="mock-sim",
    )


def _rule_based(snapshot: dict) -> VisionAnalysis:
    """Last-resort fallback when the VLM is unavailable: brightness heuristic only."""
    b = float(snapshot.get("mean_brightness", 0))
    return VisionAnalysis(lights_on=b > 90, description=f"VLM unavailable - brightness heuristic only (mean {b:.0f}/255).",
                          confidence=0.3, provider="rule-based", needs_human_review=True)


class VisionAnalyzer:
    def __init__(self, settings: Settings):
        self.s = settings
        self.provider = settings.vlm_provider.lower()
        self.model = get_chat_model(settings, vision=True) if self.provider in ("openai", "gemini", "ollama") else None
        if self.provider not in ("mock",) and self.model is None and self.provider != "ollama":
            log.warning("VLM provider '%s' unavailable -> using mock/rule-based vision", self.provider)

    @property
    def name(self) -> str:
        if self.model is not None:
            return {"openai": self.s.openai_vision_model, "gemini": self.s.gemini_vision_model,
                    "ollama": self.s.ollama_vision_model}.get(self.provider, self.provider)
        return "mock"

    async def analyze(self, snapshot: dict, focus: str | None = None) -> VisionAnalysis:
        b64 = snapshot["image_b64"]
        try:
            if self.model is not None:
                va = await asyncio.wait_for(self._langchain(b64, focus), self.s.vlm_timeout_s)
            elif self.provider == "ollama":
                va = await asyncio.wait_for(self._ollama_http(b64, focus), self.s.vlm_timeout_s)
            else:
                va = _mock_from_truth(snapshot.get("sim_truth"))
        except Exception as e:  # noqa: BLE001
            log.warning("VLM failed (%s) - rule-based fallback", e)
            va = _rule_based(snapshot)
            va.description += f" (error: {str(e)[:120]})"
        return ground(va, snapshot)

    async def _langchain(self, b64: str, focus: str | None) -> VisionAnalysis:
        msgs = [SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=[{"type": "text", "text": _user_prompt(focus)},
                                      {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}])]
        last_err = None
        for _ in range(2):  # one retry on invalid JSON
            resp = await self.model.ainvoke(msgs)
            try:
                data = extract_json(message_text(resp))
                return VisionAnalysis(**data, provider=self.name)
            except Exception as e:  # noqa: BLE001
                last_err = e
                msgs.append(HumanMessage(content="Your previous answer was not valid JSON for the schema. Reply with JSON only."))
        raise ValueError(f"invalid VLM JSON: {last_err}")

    async def _ollama_http(self, b64: str, focus: str | None) -> VisionAnalysis:
        async with httpx.AsyncClient(timeout=self.s.vlm_timeout_s) as c:
            r = await c.post(f"{self.s.ollama_base_url}/api/chat", json={
                "model": self.s.ollama_vision_model, "stream": False, "format": "json",
                "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                             {"role": "user", "content": _user_prompt(focus), "images": [b64]}]})
            r.raise_for_status()
            data = extract_json(r.json()["message"]["content"])
        return VisionAnalysis(**data, provider=f"ollama:{self.s.ollama_vision_model}")


def ground(va: VisionAnalysis, snapshot: dict) -> VisionAnalysis:
    """Cross-check the VLM against cheap sensor evidence; flag disagreements for human review."""
    notes = []
    b = snapshot.get("mean_brightness")
    if b is not None:
        if va.lights_on and b < 35:
            notes.append(f"VLM says lights ON but image is very dark (brightness {b:.0f})")
        if not va.lights_on and not va.projector_on and b > 200:
            notes.append(f"VLM says lights OFF but image is very bright (brightness {b:.0f})")
    if va.confidence < 0.6:
        notes.append("low VLM confidence")
    if notes:
        va.needs_human_review = True
        va.description = (va.description + " [review: " + "; ".join(notes) + "]").strip()
    return va


def decode_image(b64: str) -> bytes:
    return base64.b64decode(b64)
