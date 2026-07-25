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
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://acknowledged-slim-role-sandy.trycloudflare.com",
    ]

    # LLM Provider (OpenAI-compatible — any provider)
    llm_api_key: str = ""
    llm_model: str = "Qwen/Qwen3-14B"
    llm_base_url: str = ""
    # Tools mode: "native" (default, works with OpenAI/Anthropic/most providers)
    # or "prompt" (inject tools as text in system prompt — needed for Groq
    # free-tier, Gemini OpenAI-compat endpoint, and providers lacking native
    # tool_calls support)
    llm_tools_mode: str = "native"

    # ElevenLabs Voice (TTS + STT) — optional
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "Xb7hH8MSUJpSbSDYk0k2"
    elevenlabs_agent_id: str = ""

    # Cloudinary (audio storage) — optional
    cloudinary_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
