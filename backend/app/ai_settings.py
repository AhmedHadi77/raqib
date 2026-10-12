"""AI settings changed from the app (admin only): pick Gemini / OpenAI / Ollama, paste a key, test it.

The values are written into backend/.env (other lines are kept as they are) and applied immediately,
so the planner, the photo analysis and voice typing switch over without restarting the server.
"""
from __future__ import annotations

import re
from pathlib import Path

from .config import BACKEND_DIR, Settings

ENV_PATH = BACKEND_DIR / ".env"
PROVIDERS = ("none", "gemini", "openai", "ollama")
PACKAGES = {"gemini": "langchain_google_genai", "openai": "langchain_openai", "ollama": "langchain_ollama"}
HELP = {
    "gemini": "Free key: open aistudio.google.com/apikey, sign in with Google, press Create API key, copy it here.",
    "openai": "Paid key: platform.openai.com/api-keys. Best accuracy, costs a few cents a day in normal use.",
    "ollama": "Free and offline on this PC. Install Ollama, then run: ollama pull llama3.1 and ollama pull qwen2.5vl",
    "none": "Built-in offline planner: understands the listed commands and any chain of them, no photo understanding.",
}


def mask(key: str | None) -> str | None:
    if not key:
        return None
    return ("•" * 6) + key[-4:] if len(key) > 8 else "•" * len(key)


def package_ok(provider: str) -> bool:
    mod = PACKAGES.get(provider)
    if not mod:
        return True
    try:
        __import__(mod)
        return True
    except Exception:  # noqa: BLE001
        return False


def current(s: Settings, active: dict) -> dict:
    return {
        "provider": s.llm_provider if s.llm_provider in PROVIDERS else "none",
        "vision_provider": s.vlm_provider,
        "stt_provider": s.stt_provider,
        "google_api_key": mask(s.google_api_key),
        "openai_api_key": mask(s.openai_api_key),
        "gemini_model": s.gemini_model,
        "openai_model": s.openai_model,
        "ollama_base_url": s.ollama_base_url,
        "ollama_model": s.ollama_model,
        "ollama_vision_model": s.ollama_vision_model,
        "packages": {p: package_ok(p) for p in PACKAGES},
        "help": HELP,
        "active": active,
        "env_file": str(ENV_PATH),
    }


def write_env(values: dict[str, str]) -> None:
    """Update KEY=value lines in backend/.env in place (append missing ones); keep everything else."""
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    done = set()
    for i, line in enumerate(lines):                       # every active KEY= line gets the new value
        m = re.match(r"\s*([A-Z0-9_]+)\s*=", line)
        if m and m.group(1) in values:
            lines[i] = f"{m.group(1)}={values[m.group(1)]}"
            done.add(m.group(1))
    for i, line in enumerate(lines):                       # else re-use a commented-out "# KEY=" line
        m = re.match(r"\s*#\s*([A-Z0-9_]+)\s*=", line)
        if m and m.group(1) in values and m.group(1) not in done:
            lines[i] = f"{m.group(1)}={values[m.group(1)]}"
            done.add(m.group(1))
    missing = [k for k in values if k not in done]
    if missing:
        lines += ["", "# ---- set from the app (AI settings)"] + [f"{k}={values[k]}" for k in missing]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def apply(s: Settings, body: dict) -> dict[str, str]:
    """Validate the request, update the live settings object and return the .env lines to write."""
    provider = str(body.get("provider") or s.llm_provider).lower()
    if provider not in PROVIDERS:
        raise ValueError(f"provider must be one of {', '.join(PROVIDERS)}")
    env: dict[str, str] = {}
    for field, key in (("google_api_key", "GOOGLE_API_KEY"), ("openai_api_key", "OPENAI_API_KEY")):
        v = body.get(field)
        if v is not None and not str(v).startswith("•"):
            v = str(v).strip()
            if v and not re.fullmatch(r"[A-Za-z0-9_\-\.]{10,200}", v):
                raise ValueError("that key doesn't look right: paste only the key itself")
            setattr(s, field, v or None)
            env[key] = v
    for field, key in (("ollama_model", "OLLAMA_MODEL"), ("ollama_vision_model", "OLLAMA_VISION_MODEL"),
                       ("ollama_base_url", "OLLAMA_BASE_URL"), ("gemini_model", "GEMINI_MODEL"),
                       ("openai_model", "OPENAI_MODEL")):
        v = body.get(field)
        if v:
            v = str(v).strip()
            if not re.fullmatch(r"[A-Za-z0-9_\-\.:/]{1,120}", v):
                raise ValueError(f"invalid {field}")
            setattr(s, field, v)
            env[key] = v
            if field == "gemini_model":
                s.gemini_vision_model = v
                env["GEMINI_VISION_MODEL"] = v
            if field == "openai_model":
                s.openai_vision_model = v
                env["OPENAI_VISION_MODEL"] = v
    if provider == "gemini" and not s.google_api_key:
        raise ValueError("paste your Gemini API key first")
    if provider == "openai" and not s.openai_api_key:
        raise ValueError("paste your OpenAI API key first")
    if provider != "none" and not package_ok(provider):
        raise ValueError(f"the {provider} package isn't installed on the server: run upgrade.bat once, then try again")
    s.llm_provider = provider
    env["LLM_PROVIDER"] = provider
    if body.get("use_for_vision", True):
        s.vlm_provider = provider if provider != "none" else "mock"
        env["VLM_PROVIDER"] = s.vlm_provider
    if body.get("use_for_voice", True) and provider in ("gemini", "openai"):
        s.stt_provider = "auto"
        env["STT_PROVIDER"] = "auto"
    return env
