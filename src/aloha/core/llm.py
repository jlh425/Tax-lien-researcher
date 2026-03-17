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
                raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
            return AnthropicModel(model_name, api_key=settings.anthropic_api_key)

        case "openai":
            from pydantic_ai.models.openai import OpenAIModel

            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
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
                raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
            return GroqModel(model_name, api_key=settings.groq_api_key)

        case "openai-compatible":
            from pydantic_ai.models.openai import OpenAIModel

            if not settings.openai_compatible_base_url:
                raise ValueError(
                    "OPENAI_COMPATIBLE_BASE_URL is required "
                    "when LLM_PROVIDER=openai-compatible"
                )
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
