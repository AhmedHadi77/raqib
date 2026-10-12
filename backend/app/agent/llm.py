"""Chat-model factory (LangChain). Returns None when no LLM is configured -> rule-based planner."""
from __future__ import annotations

import logging

from ..config import Settings

log = logging.getLogger(__name__)


def get_chat_model(s: Settings, vision: bool = False):
    provider = (s.vlm_provider if vision else s.llm_provider).lower()
    try:
        if provider == "openai" and s.openai_api_key:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model=s.openai_vision_model if vision else s.openai_model,
                              api_key=s.openai_api_key, temperature=0, timeout=s.vlm_timeout_s, max_retries=1)
        if provider == "gemini" and s.google_api_key:
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(model=s.gemini_vision_model if vision else s.gemini_model,
                                          google_api_key=s.google_api_key, temperature=0, max_retries=1)
        if provider == "ollama":
            from langchain_ollama import ChatOllama

            return ChatOllama(model=s.ollama_vision_model if vision else s.ollama_model,
                              base_url=s.ollama_base_url, temperature=0)
    except Exception as e:  # noqa: BLE001
        log.warning("Could not create %s model (%s) - falling back", provider, e)
        return None
    if provider not in ("none", "mock", "rules"):
        log.warning("LLM provider '%s' selected but no API key / package available", provider)
    return None


def extract_json(text: str):
    """Pull the first JSON object/array out of an LLM reply (handles ```json fences)."""
    import json
    import re

    if not isinstance(text, str):
        text = str(text)
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("no JSON in model output")
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    end = text.rfind(closer)
    return json.loads(text[start:end + 1])


def message_text(msg) -> str:
    content = getattr(msg, "content", msg)
    if isinstance(content, list):  # gemini / multimodal returns parts
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content)
