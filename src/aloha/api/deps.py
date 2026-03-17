"""FastAPI dependency injection helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from aloha.config import Settings, settings
from aloha.db.engine import async_session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield an async database session, committing on success.

    Usage::

        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user() -> Any | None:
    """Return the authenticated user.

    Placeholder -- will be replaced by JWT validation logic.
    """
    return None


def get_settings() -> Settings:
    """Return the application settings singleton."""
    return settings
