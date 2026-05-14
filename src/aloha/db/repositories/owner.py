"""Owner repository — async CRUD for owners and entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from aloha.db.models.owner import Entity, Owner

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


class OwnerRepository:
    """Data-access layer for Owner records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, owner_id: int) -> Owner | None:
        return await self._session.get(Owner, owner_id)

    async def get_by_parcel(self, parcel_id: str) -> Sequence[Owner]:
        stmt = select(Owner).where(Owner.parcel_id == parcel_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def upsert(self, owner: Owner) -> Owner:
        merged = await self._session.merge(owner)
        await self._session.flush()
        return merged

    async def get_unresearched(self, max_depth: int = 0, limit: int = 100) -> Sequence[Owner]:
        """Fetch owners whose research depth is at or below ``max_depth``."""
        stmt = (
            select(Owner)
            .where(Owner.research_depth <= max_depth)
            .order_by(Owner.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


class EntityRepository:
    """Data-access layer for Entity records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_id: int) -> Entity | None:
        return await self._session.get(Entity, entity_id)

    async def get_by_name(self, entity_name: str, state: str | None = None) -> Entity | None:
        stmt = select(Entity).where(Entity.entity_name == entity_name)
        if state:
            stmt = stmt.where(Entity.state_of_formation == state.upper())
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def upsert(self, entity: Entity) -> Entity:
        merged = await self._session.merge(entity)
        await self._session.flush()
        return merged
