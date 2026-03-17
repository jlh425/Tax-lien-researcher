"""Parcel repository — async CRUD for the parcels table."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aloha.db.models.parcel import Parcel


class ParcelRepository:
    """Data-access layer for Parcel records.

    All methods accept an ``AsyncSession`` injected by the caller (FastAPI
    dependency or agent) so transactions are managed at the call site.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, parcel_id: str) -> Parcel | None:
        """Fetch a single parcel by primary key."""
        return await self._session.get(Parcel, parcel_id)

    async def get_many(
        self,
        *,
        state: str | None = None,
        county: str | None = None,
        research_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Parcel]:
        """Fetch parcels with optional filters."""
        stmt = select(Parcel)
        if state:
            stmt = stmt.where(Parcel.state == state.upper())
        if county:
            stmt = stmt.where(Parcel.county == county.lower())
        if research_status:
            stmt = stmt.where(Parcel.research_status == research_status)
        stmt = stmt.order_by(Parcel.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def upsert(self, parcel: Parcel) -> Parcel:
        """Insert or update a parcel (merge by primary key)."""
        merged = await self._session.merge(parcel)
        await self._session.flush()
        return merged

    async def update_status(self, parcel_id: str, status: str) -> None:
        """Update the research_status field for a parcel."""
        await self._session.execute(
            update(Parcel)
            .where(Parcel.parcel_id == parcel_id)
            .values(research_status=status)
        )

    async def mark_stale(self, older_than_hours: int = 24) -> int:
        """Mark parcels older than ``older_than_hours`` as stale.

        Returns the number of rows updated.
        """
        from sqlalchemy import func, text

        result = await self._session.execute(
            update(Parcel)
            .where(
                Parcel.data_freshness == "fresh",
                Parcel.last_crawled_at < func.now() - text(f"interval '{older_than_hours} hours'"),
            )
            .values(data_freshness="stale")
        )
        return result.rowcount

    async def count(
        self,
        *,
        state: str | None = None,
        county: str | None = None,
        research_status: str | None = None,
    ) -> int:
        """Count parcels matching optional filters."""
        from sqlalchemy import func

        stmt = select(func.count()).select_from(Parcel)
        if state:
            stmt = stmt.where(Parcel.state == state.upper())
        if county:
            stmt = stmt.where(Parcel.county == county.lower())
        if research_status:
            stmt = stmt.where(Parcel.research_status == research_status)
        result = await self._session.execute(stmt)
        return result.scalar_one()
