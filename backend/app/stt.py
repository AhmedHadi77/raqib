"""Speech-to-text for voice commands from the app.

Providers (STT_PROVIDER in .env):
  auto    - first available of: openai (OPENAI_API_KEY), gemini (GOOGLE_API_KEY), local
  openai  - Whisper API (whisper-1), ~USD 0.006 / minute
  gemini  - Gemini audio understanding (same key as the Gemini planner)
  local   - faster-whisper on this PC, free and offline (install_voice.bat; the model downloads once, ~140 MB)
  none    - voice disabled on the server (the web app can still use the browser's own speech recognition)

A vocabulary prompt with the room names and common commands is passed to the model, so
"Lecture Hall B", "IoT Lab" and "aircon" are recognised reliably.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import time
import urllib.request
from pathlib import Path

from .config import Settings

log = logging.getLogger(__name__)

VOCAB = ("Inspect the IoT Lab and Lecture Hall B, then return home. Check the aircon. Patrol all rooms. "
         "Move forward one meter. Turn left. Turn right. Look up. What did you find? Stop. Come back home.")


class STTUnavailable(Exception):
    pass


def _have_local() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


class SpeechToText:
    def __init__(self, s: Settings):
        self.s = s
        self._model = None
        self._load_lock = asyncio.Lock()
        p = (s.stt_provider or "auto").lower()
        if p == "auto":
            if s.openai_api_key:
                p = "openai"
            elif s.google_api_key:
                p = "gemini"
            elif _have_local():
                p = "local"
            else:
                p = "none"
        self.provider = p

    @property
    def name(self) -> str:
        if self.provider == "local":
            return f"local:{self.s.whisper_model}"
        return self.provider

    def vocab(self, zones: list[str]) -> str:
        from .agent.text import spoken_zone

        names = ", ".join(spoken_zone(z) for z in zones if z.lower() != "home")
        return (f"Rooms: {names}. " if names else "") + VOCAB

    async def transcribe(self, data: bytes, filename: str = "voice.m4a", mime: str = "audio/mp4",
                         zones: list[str] | None = None, language: str | None = None) -> dict:
        if not data or len(data) < 800:
            raise ValueError("the recording is empty - hold the mic button while you speak")
        t0 = time.perf_counter()
        prompt = self.vocab(zones or [])
        lang = language or self.s.stt_language or None
        if self.provider == "openai":
            text = await asyncio.to_thread(self._openai, data, filename, mime, prompt, lang)
        elif self.provider == "gemini":
            text = await asyncio.to_thread(self._gemini, data, mime, prompt, lang)
        elif self.provider == "local":
            model = await self._local_model()
            text = await asyncio.to_thread(self._local, model, data, prompt, lang)
        else:
            raise STTUnavailable("Voice recognition is not set up on the server. Run install_voice.bat on the PC "
                                 "(free, offline) or add an OpenAI / Gemini key to backend/.env.")
        return {"text": text.strip(), "provider": self.name, "ms": round((time.perf_counter() - t0) * 1000)}

    # ------------------------------------------------------------------ providers
    def _openai(self, data, filename, mime, prompt, lang) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self.s.openai_api_key)
        r = client.audio.transcriptions.create(model=self.s.openai_stt_model, file=(filename, data, mime),
                                               prompt=prompt, **({"language": lang} if lang else {}))
        return r.text

    def _gemini(self, data, mime, prompt, lang) -> str:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/{self.s.gemini_model}:generateContent"
               f"?key={self.s.google_api_key}")
        body = {"contents": [{"parts": [
            {"text": "Transcribe this voice command to a facility-inspection robot exactly, as plain text with no "
                     f"extra words. {('Language: ' + lang + '. ') if lang else ''}Vocabulary hints: {prompt}"},
            {"inline_data": {"mime_type": mime.split(";")[0] or "audio/mp4",
                             "data": base64.b64encode(data).decode()}}]}]}
        req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https endpoint
            out = json.load(resp)
        return "".join(p.get("text", "") for p in out["candidates"][0]["content"]["parts"])

    async def _local_model(self):
        if self._model is not None:
            return self._model
        async with self._load_lock:
            if self._model is None:
                def load():
                    from faster_whisper import WhisperModel

                    root = Path(self.s.data_dir) / "models"
                    root.mkdir(parents=True, exist_ok=True)
                    log.info("Loading speech model %s (first time downloads it)...", self.s.whisper_model)
                    return WhisperModel(self.s.whisper_model, device="cpu", compute_type="int8",
                                        download_root=str(root))

                self._model = await asyncio.to_thread(load)
        return self._model

    @staticmethod
    def _local(model, data, prompt, lang) -> str:
        segments, _info = model.transcribe(io.BytesIO(data), beam_size=3, vad_filter=True, initial_prompt=prompt,
                                           language=lang or None, condition_on_previous_text=False)
        return " ".join(s.text.strip() for s in segments)

    async def warm_up(self):
        """Load the local model in the background at start-up so the first command is fast."""
        if self.provider == "local":
            try:
                await self._local_model()
                log.info("Speech model ready")
            except Exception as e:  # noqa: BLE001
                log.warning("Speech model could not be loaded: %s", e)
