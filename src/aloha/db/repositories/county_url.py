"""CountyUrl repository — async CRUD for county URL resolution cache."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from aloha.db.models.county_url import CountyUrl

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CountyUrlRepository:
    """Data-access layer for CountyUrl records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_url(self, state: str, county: str, url_type: str) -> CountyUrl | None:
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
        """Insert or update a county URL keyed on (state, county, url_type)."""
        state_upper = state.upper()
        county_lower = county.lower()

        # Query by unique constraint rather than PK (UUID is auto-generated)
        stmt = select(CountyUrl).where(
            CountyUrl.state == state_upper,
            CountyUrl.county == county_lower,
            CountyUrl.url_type == url_type,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.url = url
            existing.confidence = confidence
            existing.source = source
            await self._session.flush()
            return existing

        record = CountyUrl(
            state=state_upper,
            county=county_lower,
            url_type=url_type,
            url=url,
            confidence=confidence,
            source=source,
        )
        self._session.add(record)
        await self._session.flush()
        return record
