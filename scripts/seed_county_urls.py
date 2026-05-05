"""Seed the county_urls table with known assessor/tax-collector URLs.

Usage:
    uv run python scripts/seed_county_urls.py
"""

from __future__ import annotations

import asyncio

import structlog

from aloha.db.engine import async_session_factory
from aloha.db.repositories.county_url import CountyUrlRepository
from aloha.services.county_url_resolver import _STATIC_REGISTRY

log = structlog.get_logger().bind(script="seed_county_urls")


async def main() -> None:
    """Seed all static registry URLs into the county_urls table."""
    async with async_session_factory() as session:
        repo = CountyUrlRepository(session)
        count = 0

        for (state, county, url_type), url in _STATIC_REGISTRY.items():
            await repo.upsert(
                state=state,
                county=county,
                url_type=url_type,
                url=url,
                confidence=1.0,
                source="seed",
            )
            count += 1

        await session.commit()

    log.info("seed_complete", urls_seeded=count)
    print(f"Seeded {count} county URLs into the database.")


if __name__ == "__main__":
    asyncio.run(main())
