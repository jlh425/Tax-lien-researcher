"""LLM provider resolution.

Reads ``llm_provider`` and ``llm_model`` from settings and returns a
Pydantic AI ``Model`` instance for the configured provider. Supports:

- **anthropic** — Claude models via Anthropic API
- **openai** — GPT models via OpenAI API
- **ollama** — Local models via Ollama (uses OpenAI-compatible interface)
- **groq** — Groq-hosted models
- **openai-compatible** — Any OpenAI-compatible endpoint (vLLM, LM Studio,
  llama.cpp server, Together AI, etc.)

Per-agent overrides are supported via ``LLM_AGENT_<NAME>`` env vars.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import structlog

log = structlog.get_logger().bind(component="llm")


def _build_model(provider: str, model_name: str) -> Any:
    """Construct a Pydantic AI model for the given provider and model name.

    This is the internal factory — callers should use ``get_model()`` or
    ``get_agent_model()`` instead.
    """
    from aloha.config import settings  # deferred to avoid circular imports

    match provider:
        case "anthropic":
            from pydantic_ai.models.anthropic import AnthropicModel

            if not settings.anthropic_api_key:
                log.warning("no_anthropic_api_key", model=model_name)
                return None
            return AnthropicModel(model_name, api_key=settings.anthropic_api_key)

        case "openai":
            from pydantic_ai.models.openai import OpenAIModel

            if not settings.openai_api_key:
                log.warning("no_openai_api_key", model=model_name)
                return None
            return OpenAIModel(model_name, api_key=settings.openai_api_key)

        case "ollama":
            from pydantic_ai.models.openai import OpenAIModel

            return OpenAIModel(
                model_name,
                base_url=f"{settings.ollama_base_url}/v1",
                api_key="ollama",  # Ollama doesn't need a real key
            )

        case "groq":
            from pydantic_ai.models.groq import GroqModel

            if not settings.groq_api_key:
                log.warning("no_groq_api_key", model=model_name)
                return None
            return GroqModel(model_name, api_key=settings.groq_api_key)

        case "openai-compatible":
            from pydantic_ai.models.openai import OpenAIModel

            if not settings.openai_compatible_base_url:
                log.warning("no_openai_compatible_base_url", model=model_name)
                return None
            return OpenAIModel(
                model_name,
                base_url=settings.openai_compatible_base_url,
                api_key=settings.openai_compatible_api_key or "no-key",
            )

        case _:
            raise ValueError(f"Unknown LLM provider: {provider!r}")


@lru_cache(maxsize=1)
def get_model() -> Any:
    """Build and cache the **global default** Pydantic AI model.

    Uses ``LLM_PROVIDER`` and ``LLM_MODEL`` from settings.
    """
    from aloha.config import settings

    log.info("resolving_default_llm", provider=settings.llm_provider, model=settings.llm_model)
    return _build_model(settings.llm_provider, settings.llm_model)


@lru_cache(maxsize=16)
def get_agent_model(agent_name: str) -> Any:
    """Build and cache a Pydantic AI model for a specific agent.

    Checks for a per-agent override (``LLM_AGENT_<NAME>=provider:model``).
    Falls back to the global default if no override is set.

    Args:
        agent_name: The agent key (e.g. ``"orchestrator"``, ``"scoring"``).

    Returns:
        A ``pydantic_ai.models.Model`` instance.
    """
    from aloha.config import settings

    provider, model_name = settings.get_agent_llm(agent_name)

    # If it resolves to the same as the global default, reuse that instance
    if provider == settings.llm_provider and model_name == settings.llm_model:
        return get_model()

    log.info(
        "resolving_agent_llm",
        agent=agent_name,
        provider=provider,
        model=model_name,
    )
    return _build_model(provider, model_name)


# ── Per-user BYOK model resolution ───────────────────────────────────────────


def _build_model_with_key(
    provider: str,
    model_name: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Any:
    """Build a Pydantic AI model using an explicit API key (BYOK) or Ollama URL.

    Unlike :func:`_build_model`, this does **not** read keys from env/settings.
    Supports BYOK providers: anthropic, openai, groq, ollama.
    """
    match provider:
        case "anthropic":
            from pydantic_ai.models.anthropic import AnthropicModel

            return AnthropicModel(model_name, api_key=api_key)

        case "openai":
            from pydantic_ai.models.openai import OpenAIModel

            return OpenAIModel(model_name, api_key=api_key)

        case "groq":
            from pydantic_ai.models.groq import GroqModel

            return GroqModel(model_name, api_key=api_key)

        case "ollama":
            from pydantic_ai.models.openai import OpenAIModel

            ollama_url = base_url or "http://localhost:11434"
            return OpenAIModel(
                model_name,
                base_url=f"{ollama_url.rstrip('/')}/v1",
                api_key="ollama",
            )

        case _:
            raise ValueError(f"BYOK not supported for provider: {provider!r}")


async def resolve_user_model(
    user_id: str | None,
    agent_name: str | None = None,
) -> Any | None:
    """Return a per-user Pydantic AI model, or ``None`` to fall back to server key.

    Opens its own short-lived DB session so it can be called from background
    workers that don't have a request-scoped session.

    Resolution order:
    1. ``configured_llms`` + ``active_llm_id`` (new unified schema)
    2. Legacy ``llm_provider`` / ``llm_model`` flat fields (backward compat)
    """
    if not user_id:
        return None

    from uuid import UUID

    from aloha.db.engine import async_session_factory
    from aloha.services.api_key_service import ApiKeyService

    try:
        async with async_session_factory() as session:
            svc = ApiKeyService(session)
            user = await svc._get_user(UUID(user_id))
            user_settings: dict = user.settings or {}
            llm_keys: dict = user_settings.get("llm_keys", {})

            # ── Try new configured_llms schema first ────────────────────
            configured: list[dict] = user_settings.get("configured_llms", [])
            active_id: str | None = user_settings.get("active_llm_id")
            if configured and active_id:
                entry = next(
                    (e for e in configured if e["id"] == active_id), None,
                )
                if entry:
                    provider = entry["provider"]
                    model_name = entry["model"]
                    base_url = entry.get("base_url")

                    api_key: str | None = None
                    if provider != "ollama":
                        api_key = await svc.get_decrypted_key(
                            UUID(user_id), provider,
                        )
                        if not api_key:
                            log.warning(
                                "configured_llm_missing_key",
                                user_id=user_id,
                                provider=provider,
                            )
                            # Fall through to legacy path
                        else:
                            log.info(
                                "resolved_user_model",
                                user_id=user_id,
                                provider=provider,
                                model=model_name,
                                agent=agent_name,
                                source="configured_llms",
                            )
                            return _build_model_with_key(
                                provider, model_name, api_key, base_url,
                            )
                    else:
                        log.info(
                            "resolved_user_model",
                            user_id=user_id,
                            provider="ollama",
                            model=model_name,
                            agent=agent_name,
                            source="configured_llms",
                        )
                        return _build_model_with_key(
                            "ollama", model_name, base_url=base_url,
                        )

            # ── Legacy flat fields fallback ─────────────────────────────
            preferred_provider: str | None = user_settings.get("llm_provider")
            preferred_model: str | None = user_settings.get("llm_model")

            if not preferred_provider:
                return None

            # Ollama doesn't need an API key — just a base URL
            if preferred_provider == "ollama":
                model_name = preferred_model or "llama3.1:8b"
                ollama_url = user_settings.get("ollama_base_url")
                log.info(
                    "resolved_user_model",
                    user_id=user_id,
                    provider="ollama",
                    model=model_name,
                    agent=agent_name,
                    source="legacy",
                )
                return _build_model_with_key("ollama", model_name, base_url=ollama_url)

            if preferred_provider not in llm_keys:
                return None

            api_key = await svc.get_decrypted_key(UUID(user_id), preferred_provider)
            if not api_key:
                return None

            model_name = preferred_model or "claude-sonnet-4-20250514"

            log.info(
                "resolved_user_model",
                user_id=user_id,
                provider=preferred_provider,
                model=model_name,
                agent=agent_name,
                source="legacy",
            )
            return _build_model_with_key(preferred_provider, model_name, api_key)

    except Exception:
        log.warning("user_model_resolution_failed", user_id=user_id, agent=agent_name)
        return None
