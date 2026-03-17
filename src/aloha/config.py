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

    # ── Per-Agent LLM Overrides ──────────────────────────────────────────
    # Format: LLM_AGENT_<NAME>=provider:model  (e.g. LLM_AGENT_SCORING=openai:gpt-4o)
    # Agents without an override use the global LLM_PROVIDER / LLM_MODEL.
    llm_agent_orchestrator: str | None = None
    llm_agent_database: str | None = None
    llm_agent_discovery: str | None = None
    llm_agent_parcel_research: str | None = None
    llm_agent_owner_research: str | None = None
    llm_agent_entity_research: str | None = None
    llm_agent_contact_research: str | None = None
    llm_agent_outreach: str | None = None
    llm_agent_zoning: str | None = None
    llm_agent_enrichment: str | None = None
    llm_agent_scoring: str | None = None
    llm_agent_report: str | None = None

    def get_agent_llm(self, agent_name: str) -> tuple[str, str]:
        """Return (provider, model) for a specific agent.

        Checks for a per-agent override first, falls back to the global default.
        Override format: ``"provider:model"`` (e.g. ``"openai:gpt-4o"``).
        """
        override = getattr(self, f"llm_agent_{agent_name}", None)
        if override:
            parts = override.split(":", 1)
            if len(parts) == 2:
                return parts[0], parts[1]
            # If no colon, treat as model name with the global provider
            return self.llm_provider, parts[0]
        return self.llm_provider, self.llm_model

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
