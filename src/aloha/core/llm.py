"""LLM provider resolution.

Reads ``llm_provider`` and ``llm_model`` from settings and returns a
Pydantic AI ``Model`` instance for the configured provider. Supports:

- **anthropic** — Claude models via Anthropic API
- **openai** — GPT models via OpenAI API
- **ollama** — Local models via Ollama (uses OpenAI-compatible interface)
- **groq** — Groq-hosted models
- **openai-compatible** — Any OpenAI-compatible endpoint (vLLM, LM Studio,
  llama.cpp server, Together AI, etc.)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import structlog

log = structlog.get_logger().bind(component="llm")


@lru_cache(maxsize=1)
def get_model() -> Any:
    """Build and cache a Pydantic AI model from application settings.

    Returns:
        A ``pydantic_ai.models.Model`` instance ready for use with agents.

    Raises:
        ValueError: If the configured provider is unknown or the required
            API key / base URL is missing.
    """
    from aloha.config import settings  # deferred to avoid circular imports

    provider = settings.llm_provider
    model_name = settings.llm_model

    log.info("resolving_llm", provider=provider, model=model_name)

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
