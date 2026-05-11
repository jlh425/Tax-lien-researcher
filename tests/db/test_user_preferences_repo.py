"""Tests for UserPreferencesRepository — unit tests with mocked AsyncSession."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from aloha.db.models.user_preferences import UserPreferences
from aloha.db.repositories.user_preferences import UserPreferencesRepository


def _mock_session() -> AsyncMock:
    """Return an AsyncMock that behaves like an AsyncSession."""
    session = AsyncMock()
    session.add = MagicMock()
    return session


def _mock_result(row: UserPreferences | None) -> MagicMock:
    """Wrap a model (or None) in a mock Result with scalar_one_or_none."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    return result


class TestGetByUserId:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_prefs(self) -> None:
        session = _mock_session()
        session.execute.return_value = _mock_result(None)

        repo = UserPreferencesRepository(session)
        result = await repo.get_by_user_id(uuid.uuid4())

        assert result is None
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_existing_prefs(self) -> None:
        user_id = uuid.uuid4()
        prefs = MagicMock(spec=UserPreferences)
        prefs.user_id = user_id
        prefs.scoring_weights = {"lien_to_value": 40}
        prefs.api_keys = {"google_maps": "AIza-key"}

        session = _mock_session()
        session.execute.return_value = _mock_result(prefs)

        repo = UserPreferencesRepository(session)
        result = await repo.get_by_user_id(user_id)

        assert result is not None
        assert result.scoring_weights == {"lien_to_value": 40}
        assert result.api_keys == {"google_maps": "AIza-key"}


class TestUpsert:
    @pytest.mark.asyncio
    async def test_creates_new_record_when_none_exists(self) -> None:
        user_id = uuid.uuid4()
        session = _mock_session()
        session.execute.return_value = _mock_result(None)

        repo = UserPreferencesRepository(session)
        weights = {"lien_to_value": 50, "redemption_urgency": 50}
        await repo.upsert(
            user_id, scoring_weights=weights, api_keys={"google_maps": "key"}
        )

        # A new record should have been added to the session
        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert isinstance(added, UserPreferences)
        assert added.user_id == user_id
        assert added.scoring_weights == weights
        assert added.api_keys == {"google_maps": "key"}
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_updates_existing_scoring_weights(self) -> None:
        user_id = uuid.uuid4()
        existing = UserPreferences(
            user_id=user_id,
            scoring_weights={"lien_to_value": 25},
            api_keys={"google_maps": "old"},
        )
        session = _mock_session()
        session.execute.return_value = _mock_result(existing)

        repo = UserPreferencesRepository(session)
        new_weights = {"lien_to_value": 60}
        result = await repo.upsert(user_id, scoring_weights=new_weights)

        assert result.scoring_weights == {"lien_to_value": 60}
        # api_keys should be untouched (None was passed)
        assert result.api_keys == {"google_maps": "old"}
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_updates_existing_api_keys(self) -> None:
        user_id = uuid.uuid4()
        existing = UserPreferences(
            user_id=user_id,
            scoring_weights={"lien_to_value": 25},
            api_keys={},
        )
        session = _mock_session()
        session.execute.return_value = _mock_result(existing)

        repo = UserPreferencesRepository(session)
        result = await repo.upsert(
            user_id, api_keys={"google_maps": "new-key"}
        )

        assert result.api_keys == {"google_maps": "new-key"}
        # scoring_weights should be untouched
        assert result.scoring_weights == {"lien_to_value": 25}

    @pytest.mark.asyncio
    async def test_creates_with_empty_defaults_when_none_passed(self) -> None:
        user_id = uuid.uuid4()
        session = _mock_session()
        session.execute.return_value = _mock_result(None)

        repo = UserPreferencesRepository(session)
        await repo.upsert(user_id)

        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert added.scoring_weights == {}
        assert added.api_keys == {}
