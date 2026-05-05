"""CountyUrl repository — async CRUD for county URL resolution cache."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aloha.db.models.county_url import CountyUrl


class CountyUrlRepository:
    """Data-access layer for CountyUrl records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_url(
        self, state: str, county: str, url_type: str
    ) -> CountyUrl | None:
        """Get the highest-confidence URL for a county + url_type."""
        stmt = (
            select(CountyUrl)
            .where(
                CountyUrl.state == state.upper(),
                CountyUrl.county == county.lower(),
                CountyUrl.url_type == url_type,
            )
            .order_by(CountyUrl.confidence.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        state: str,
        county: str,
        url_type: str,
        url: str,
        confidence: float = 1.0,
        source: str = "seed",
    ) -> CountyUrl:
        """Insert or update a county URL (merge on unique constraint)."""
        record = CountyUrl(
            state=state.upper(),
            county=county.lower(),
            url_type=url_type,
            url=url,
            confidence=confidence,
            source=source,
        )
        merged = await self._session.merge(record)
        await self._session.flush()
        return merged
