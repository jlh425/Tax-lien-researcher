"""UserPreferences repository — async CRUD for user scoring weights and API keys."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from aloha.db.models.user_preferences import UserPreferences

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class UserPreferencesRepository:
    """Data-access layer for UserPreferences records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> UserPreferences | None:
        """Return the preferences row for a user, or None if not set."""
        stmt = select(UserPreferences).where(UserPreferences.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        user_id: uuid.UUID,
        *,
        scoring_weights: dict | None = None,
        api_keys: dict | None = None,
    ) -> UserPreferences:
        """Create or update preferences for a user.

        Only the provided fields are overwritten; pass ``None`` to leave
        a field unchanged.
        """
        stmt = select(UserPreferences).where(UserPreferences.user_id == user_id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            if scoring_weights is not None:
                existing.scoring_weights = scoring_weights
            if api_keys is not None:
                existing.api_keys = api_keys
            await self._session.flush()
            return existing

        record = UserPreferences(
            user_id=user_id,
            scoring_weights=scoring_weights or {},
            api_keys=api_keys or {},
        )
        self._session.add(record)
        await self._session.flush()
        return record
