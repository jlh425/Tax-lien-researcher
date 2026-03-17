"""Application configuration via Pydantic BaseSettings."""

from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration loaded from environment variables / .env file."""

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://localhost:5432/aloha"
    database_url_sync: str = "postgresql+psycopg2://localhost:5432/aloha"
    redis_url: str = "redis://localhost:6379/0"

    # ── Auth / Security ───────────────────────────────────────────────────
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ── LLM Provider ──────────────────────────────────────────────────────
    # Supported providers: anthropic, openai, ollama, groq, openai-compatible
    llm_provider: Literal[
        "anthropic", "openai", "ollama", "groq", "openai-compatible"
    ] = "anthropic"
    llm_model: str = "claude-sonnet-4-20250514"

    # Provider API keys (set the one matching your llm_provider)
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    groq_api_key: str | None = None

    # For ollama or any OpenAI-compatible endpoint (vLLM, LM Studio, etc.)
    ollama_base_url: str = "http://localhost:11434"
    openai_compatible_base_url: str | None = None
    openai_compatible_api_key: str | None = None

    # ── Observability ─────────────────────────────────────────────────────
    sentry_dsn: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None

    # ── Billing ───────────────────────────────────────────────────────────
    stripe_secret_key: str | None = None
    stripe_publishable_key: str | None = None
    stripe_webhook_secret: str | None = None

    # ── Comms ─────────────────────────────────────────────────────────────
    sendgrid_api_key: str | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None

    # ── Runtime ───────────────────────────────────────────────────────────
    environment: str = "development"
    log_level: str = "DEBUG"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
