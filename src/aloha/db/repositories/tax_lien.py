"""TaxLien repository — async CRUD for the tax_liens table."""

from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aloha.db.models.tax_lien import TaxLien


class TaxLienRepository:
    """Data-access layer for TaxLien records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, lien_id: int) -> TaxLien | None:
        return await self._session.get(TaxLien, lien_id)

    async def get_by_parcel(self, parcel_id: str) -> Sequence[TaxLien]:
        stmt = select(TaxLien).where(TaxLien.parcel_id == parcel_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_active(
        self,
        *,
        instrument_type: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> Sequence[TaxLien]:
        """Fetch active liens/deeds, optionally filtered by instrument type."""
        stmt = select(TaxLien).where(TaxLien.lien_status == "active")
        if instrument_type:
            stmt = stmt.where(TaxLien.instrument_type == instrument_type)
        stmt = stmt.order_by(TaxLien.retrieved_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_upcoming_deadlines(self, within_days: int = 60) -> Sequence[TaxLien]:
        """Fetch lien certificates whose redemption deadline is within N days."""
        from sqlalchemy import func, text

        stmt = (
            select(TaxLien)
            .where(
                TaxLien.instrument_type == "lien_certificate",
                TaxLien.lien_status == "active",
                TaxLien.redemption_deadline.isnot(None),
                TaxLien.redemption_deadline
                <= func.current_date() + text(f"interval '{within_days} days'"),
            )
            .order_by(TaxLien.redemption_deadline.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_upcoming_auctions(self, within_days: int = 30) -> Sequence[TaxLien]:
        """Fetch tax deeds with an auction date within N days."""
        from sqlalchemy import func, text

        stmt = (
            select(TaxLien)
            .where(
                TaxLien.instrument_type == "tax_deed",
                TaxLien.lien_status.in_(["scheduled_auction"]),
                TaxLien.auction_date.isnot(None),
                TaxLien.auction_date
                <= func.current_date() + text(f"interval '{within_days} days'"),
            )
            .order_by(TaxLien.auction_date.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def upsert(self, lien: TaxLien) -> TaxLien:
        merged = await self._session.merge(lien)
        await self._session.flush()
        return merged

    async def update_status(self, lien_id: int, status: str) -> None:
        await self._session.execute(
            update(TaxLien).where(TaxLien.id == lien_id).values(lien_status=status)
        )
