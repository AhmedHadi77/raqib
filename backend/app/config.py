"""Backend settings - read from environment variables or backend/.env"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    # --- robot / MQTT -------------------------------------------------------
    robot_id: str = "robot01"
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_tls: bool = False
    mqtt_ca_cert: str | None = None
    mqtt_username: str | None = "backend"
    mqtt_password: str | None = "backend-secret"
    embedded_broker: bool = False          # start a dev broker inside the backend (no Docker needed)
    discovery_beacon: bool = True          # announce the server on the LAN so robots with mqtt.host=auto find it
    api_port: int = 8000                   # port the app/API listens on (sent in the discovery beacon)
    heartbeat_interval_s: float = 2.0
    command_timeout_s: float = 20.0
    navigation_timeout_s: float = 120.0

    # --- security -------------------------------------------------------------
    jwt_secret: str = "CHANGE-ME-to-a-long-random-string"
    jwt_expire_hours: int = 12
    # users "name:password:role" separated by commas. roles: admin | operator | viewer
    users: str = "admin:admin123:admin,operator:operator123:operator,viewer:viewer123:viewer"
    cors_origins: str = "*"

    # --- AI -------------------------------------------------------------------
    # LLM used to PLAN commands + write summaries: none | openai | gemini | ollama
    llm_provider: str = "none"
    # VLM used to analyse snapshots: mock | openai | gemini | ollama
    vlm_provider: str = "mock"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    openai_vision_model: str = "gpt-4o"
    google_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_vision_model: str = "gemini-2.5-flash"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_vision_model: str = "qwen2.5vl"
    vlm_timeout_s: float = 30.0

    # --- voice (speech-to-text for spoken commands) ------------------------------
    # auto | openai | gemini | local | none   (local = faster-whisper, free + offline)
    stt_provider: str = "auto"
    stt_language: str | None = "en"         # "en"; set to null and WHISPER_MODEL=base for other languages
    whisper_model: str = "base.en"          # tiny.en (fastest) | base.en | small.en (most accurate)
    openai_stt_model: str = "whisper-1"

    # --- exam proctoring (monitor mode) --------------------------------------------
    # auto = simulator truth > MediaPipe on this PC > vision AI ; mediapipe | ai | off
    proctor_vision: str = "auto"
    proctor_ai_checks: bool = True          # also ask the vision AI about notes / earpieces (once per view)
    proctor_head_turn_deg: float = 35.0     # head turned further than this ...
    proctor_head_turn_s: float = 3.0        # ... for this long = flag
    proctor_look_down_deg: float = 40.0     # head bowed further than this ...
    proctor_look_down_s: float = 8.0        # ... for this long = flag
    proctor_dwell_s: float = 4.0            # seconds the camera watches each view (longer if something looks odd)
    proctor_approach: bool = True           # drive up to a flagged student before speaking

    # --- product / site -------------------------------------------------------------
    product_name: str = "Raqib"
    site_name: str = "Main Campus"

    # --- memory -----------------------------------------------------------------
    data_dir: str = str(BACKEND_DIR / "data")
    chroma_mode: str = "embedded"           # embedded | http
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    # auto | sentence-transformers | chroma-default | hash
    embedding_backend: str = "auto"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- environment thresholds (same defaults as edge/config.yaml) ----------------
    comfort_temp_min: float = 22.0
    comfort_temp_max: float = 26.0
    comfort_rh_min: float = 40.0
    comfort_rh_max: float = 60.0

    @property
    def user_table(self) -> dict[str, tuple[str, str]]:
        out = {}
        for item in self.users.split(","):
            item = item.strip()
            if item.count(":") >= 2:
                name, pw, role = item.split(":", 2)
                out[name] = (pw, role)
        return out


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    Path(s.data_dir).mkdir(parents=True, exist_ok=True)
    (Path(s.data_dir) / "images").mkdir(parents=True, exist_ok=True)
    return s
