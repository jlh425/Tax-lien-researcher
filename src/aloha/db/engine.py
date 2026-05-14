"""SQLAlchemy async engine and session factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from aloha.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=(settings.environment == "development"),
    pool_size=5,
    max_overflow=10,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session for dependency injection.

    Usage with FastAPI::

        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_session)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            # Catch-all: rollback on any error to keep the session clean
            await session.rollback()
            raise
