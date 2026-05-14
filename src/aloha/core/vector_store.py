"""Qdrant vector store wrapper for document chunk embeddings.

Provides async upsert / search / delete against a Qdrant collection,
with graceful degradation (log + return empty) on errors so the rest
of the pipeline is never blocked by a vector-store outage.
"""

from __future__ import annotations

from typing import Any

import structlog

log = structlog.get_logger().bind(component="vector_store")

try:
    from qdrant_client import AsyncQdrantClient, models
except ImportError:  # pragma: no cover
    AsyncQdrantClient = None  # type: ignore[assignment,misc]
    models = None  # type: ignore[assignment]

_client: AsyncQdrantClient | None = None


def get_vector_store() -> AsyncQdrantClient | None:
    """Return a singleton async Qdrant client, or ``None`` if unavailable."""
    global _client  # noqa: PLW0603
    if AsyncQdrantClient is None:
        return None
    if _client is None:
        from aloha.config import settings

        _client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
    return _client


async def ensure_collection() -> None:
    """Create the Qdrant collection if it does not already exist."""
    client = get_vector_store()
    if client is None:
        return
    from aloha.config import settings

    try:
        exists = await client.collection_exists(settings.qdrant_collection)
        if not exists:
            await client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=models.VectorParams(
                    size=settings.embedding_dimensions,
                    distance=models.Distance.COSINE,
                ),
            )
            log.info("qdrant_collection_created", collection=settings.qdrant_collection)
    except Exception as exc:
        # Catch-all: graceful degradation so vector-store outage never blocks pipeline
        log.warning("qdrant_ensure_collection_failed", error=str(exc))


async def upsert(
    chunk_id: int,
    vector: list[float],
    metadata: dict[str, Any] | None = None,
) -> None:
    """Upsert a single point into Qdrant using the PG chunk id."""
    client = get_vector_store()
    if client is None:
        return
    from aloha.config import settings

    try:
        await client.upsert(
            collection_name=settings.qdrant_collection,
            points=[
                models.PointStruct(
                    id=chunk_id,
                    vector=vector,
                    payload=metadata or {},
                ),
            ],
        )
    except Exception as exc:
        # Catch-all: graceful degradation so vector-store outage never blocks pipeline
        log.warning("qdrant_upsert_failed", chunk_id=chunk_id, error=str(exc))


async def search(
    query_vector: list[float],
    *,
    limit: int = 10,
    filter_conditions: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Cosine-similarity search. Returns ``[{id, score, payload}, ...]``."""
    client = get_vector_store()
    if client is None:
        return []
    from aloha.config import settings

    qdrant_filter = None
    if filter_conditions:
        must = [
            models.FieldCondition(
                key=k,
                match=models.MatchValue(value=v),
            )
            for k, v in filter_conditions.items()
        ]
        qdrant_filter = models.Filter(must=must)

    try:
        results = await client.query_points(
            collection_name=settings.qdrant_collection,
            query=query_vector,
            query_filter=qdrant_filter,
            limit=limit,
        )
        return [
            {"id": point.id, "score": point.score, "payload": point.payload}
            for point in results.points
        ]
    except Exception as exc:
        # Catch-all: graceful degradation so vector-store outage never blocks pipeline
        log.warning("qdrant_search_failed", error=str(exc))
        return []


async def delete(chunk_ids: list[int]) -> None:
    """Remove points by their PG chunk IDs."""
    client = get_vector_store()
    if client is None or not chunk_ids:
        return
    from aloha.config import settings

    try:
        await client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=models.PointIdsList(points=chunk_ids),
        )
    except Exception as exc:
        # Catch-all: graceful degradation so vector-store outage never blocks pipeline
        log.warning("qdrant_delete_failed", chunk_ids=chunk_ids, error=str(exc))
