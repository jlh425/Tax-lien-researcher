"""Text embedding utility — configurable provider (OpenAI or Ollama).

Produces vectors whose dimensionality is controlled by ``settings.embedding_dimensions``
(default 1536 for OpenAI text-embedding-3-small, 1024 for mxbai-embed-large via Ollama).

The Ollama path uses the OpenAI SDK pointed at the Ollama-compatible ``/v1`` endpoint,
so ``openai`` must be installed for *both* providers.

Returns ``None`` gracefully when the provider SDK is missing or the API call fails.
"""

from __future__ import annotations

import structlog

from aloha.config import settings

log = structlog.get_logger().bind(component="embeddings")

# Optional import — module starts without openai installed (e.g. CI).
try:
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover
    AsyncOpenAI = None  # type: ignore[assignment,misc]


async def embed_text(text: str) -> list[float] | None:
    """Embed *text* using the configured provider.

    Returns a list of floats suitable for Qdrant storage, or ``None``
    if the provider is not configured or any error occurs.
    """
    if AsyncOpenAI is None:
        log.debug("openai_sdk_not_installed")
        return None

    match settings.embedding_provider:
        case "openai":
            return await _embed_openai(text, settings)
        case "ollama":
            return await _embed_ollama(text, settings)
        case _:
            log.warning("unknown_embedding_provider", provider=settings.embedding_provider)
            return None


async def _embed_openai(text: str, settings: object) -> list[float] | None:
    """Embed via the OpenAI embeddings API."""
    api_key = getattr(settings, "openai_api_key", None)
    if not api_key:
        log.debug("openai_api_key_not_set")
        return None
    try:
        client = AsyncOpenAI(api_key=api_key)
        resp = await client.embeddings.create(
            model=settings.embedding_model,  # type: ignore[union-attr]
            input=text,
            dimensions=settings.embedding_dimensions,  # type: ignore[union-attr]
        )
        return resp.data[0].embedding
    except Exception as exc:
        log.warning("embedding_failed", provider="openai", error=str(exc))
        return None


async def _embed_ollama(text: str, settings: object) -> list[float] | None:
    """Embed via Ollama's OpenAI-compatible ``/v1`` endpoint."""
    base_url = getattr(settings, "ollama_embedding_url", "http://localhost:11434")
    try:
        client = AsyncOpenAI(base_url=f"{base_url}/v1", api_key="ollama")
        resp = await client.embeddings.create(
            model=settings.embedding_model,  # type: ignore[union-attr]
            input=text,
        )
        return resp.data[0].embedding
    except Exception as exc:
        log.warning("embedding_failed", provider="ollama", error=str(exc))
        return None
