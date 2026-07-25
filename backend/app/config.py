"""Application configuration via pydantic-settings.

Settings are loaded from environment variables with .env fallback.
Priority: explicit env var > .env file > class default.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    app_name: str = "ProteccionInteligente360"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///data/proteccion360.db"
    app_profile: str = "original"
    multicanal_deployment_id: str = ""
    multicanal_root: str = "/app/multicanal-data"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # LLM Provider (OpenAI-compatible — any provider)
    llm_api_key: str = ""
    llm_model: str = "Qwen/Qwen3-14B"
    llm_base_url: str = ""

    # ElevenLabs Voice (TTS + STT) — optional
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "Xb7hH8MSUJpSbSDYk0k2"
    elevenlabs_agent_id: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
