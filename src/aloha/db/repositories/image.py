"""Repositories for PropertyImage and DocumentChunk models."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from aloha.db.models.document_chunk import DocumentChunk
from aloha.db.models.property_image import PropertyImage


class PropertyImageRepository:
    """Data-access layer for PropertyImage records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_parcel(self, parcel_id: str) -> Sequence[PropertyImage]:
        """Return all images for a parcel, ordered by id."""
        result = await self._session.execute(
            sa_select(PropertyImage)
            .where(PropertyImage.parcel_id == parcel_id)
            .order_by(PropertyImage.id)
        )
        return result.scalars().all()

    async def upsert(self, image: PropertyImage) -> PropertyImage:
        """Insert or update a PropertyImage (merge by primary key)."""
        merged = await self._session.merge(image)
        await self._session.flush()
        return merged


class DocumentChunkRepository:
    """Data-access layer for DocumentChunk records (RAG store)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, chunk: DocumentChunk) -> DocumentChunk:
        """Persist a new DocumentChunk and flush."""
        self._session.add(chunk)
        await self._session.flush()
        return chunk

    async def get_by_parcel(self, parcel_id: str) -> Sequence[DocumentChunk]:
        """Return all chunks for a parcel, ordered by creation time."""
        result = await self._session.execute(
            sa_select(DocumentChunk)
            .where(DocumentChunk.parcel_id == parcel_id)
            .order_by(DocumentChunk.created_at)
        )
        return result.scalars().all()

    async def search_similar(
        self,
        query_embedding: list[float],
        *,
        limit: int = 10,
        parcel_id: str | None = None,
    ) -> Sequence[DocumentChunk]:
        """Cosine similarity search via pgvector HNSW index.

        Returns [] if pgvector is not installed (e.g. plain Postgres in CI).
        """
        try:
            from pgvector.sqlalchemy import Vector  # noqa: F401
        except ImportError:
            return []

        stmt = sa_select(DocumentChunk)
        if parcel_id:
            stmt = stmt.where(DocumentChunk.parcel_id == parcel_id)
        stmt = stmt.order_by(DocumentChunk.embedding.cosine_distance(query_embedding)).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()
