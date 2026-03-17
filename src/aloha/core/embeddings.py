"""OpenAI text embedding utility.

Produces 1536-dimensional vectors via text-embedding-3-small to match the
existing ``document_chunks.embedding vector(1536)`` pgvector column.

Returns None gracefully when:
- ``OPENAI_API_KEY`` is not configured
- The OpenAI API call fails for any reason

This allows the rest of the pipeline to continue without embeddings (the
DocumentChunk will be stored with embedding=None, which pgvector allows).
"""

from __future__ import annotations

import structlog

log = structlog.get_logger().bind(component="embeddings")


async def embed_text(text: str) -> list[float] | None:
    """Embed *text* using OpenAI text-embedding-3-small (1536 dims).

    Returns a list of 1536 floats suitable for pgvector storage, or None
    if the API key is not configured or any error occurs.
    """
    from aloha.config import settings

    if not settings.openai_api_key:
        return None

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        resp = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            dimensions=1536,  # explicit — must match document_chunks.embedding vector(1536)
        )
        return resp.data[0].embedding
    except Exception as exc:
        log.warning("embedding_failed", error=str(exc))
        return None
