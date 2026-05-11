"""Tests for user preferences (scoring weights / API keys) settings routes."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from aloha.api.deps import require_user
from aloha.api.routes.settings import _preferences_repo

if TYPE_CHECKING:
    from fastapi import FastAPI


def _fake_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    return user


def _make_test_app(
    mock_repo: AsyncMock | None = None,
    user: MagicMock | None = None,
) -> FastAPI:
    """Build a minimal FastAPI app with settings router and overridden deps."""
    from fastapi import FastAPI

    from aloha.api.routes.settings import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    _user = user or _fake_user()
    app.dependency_overrides[require_user] = lambda: _user

    if mock_repo is not None:
        app.dependency_overrides[_preferences_repo] = lambda: mock_repo

    return app


class TestGetPreferences:
    @pytest.mark.asyncio
    async def test_returns_defaults_when_no_prefs_exist(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.get_by_user_id.return_value = None

        app = _make_test_app(mock_repo)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings/preferences")

        assert resp.status_code == 200
        data = resp.json()
        assert data["scoring_weights"]["lien_to_value"] == 25
        assert data["scoring_weights"]["redemption_urgency"] == 25
        assert data["scoring_weights"]["owner_motivation"] == 25
        assert data["scoring_weights"]["contact_reachability"] == 25
        assert data["api_keys"]["google_maps"] is None
        assert data["include_screenshots"] is True

    @pytest.mark.asyncio
    async def test_returns_existing_prefs(self) -> None:
        prefs = MagicMock()
        prefs.scoring_weights = {
            "lien_to_value": 40,
            "redemption_urgency": 20,
            "owner_motivation": 20,
            "contact_reachability": 20,
            "include_screenshots": False,
        }
        prefs.api_keys = {"google_maps": "AIza-masked"}

        mock_repo = AsyncMock()
        mock_repo.get_by_user_id.return_value = prefs

        app = _make_test_app(mock_repo)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings/preferences")

        assert resp.status_code == 200
        data = resp.json()
        assert data["scoring_weights"]["lien_to_value"] == 40
        assert data["api_keys"]["google_maps"] == "AIza-masked"
        assert data["include_screenshots"] is False


class TestPutPreferences:
    @pytest.mark.asyncio
    async def test_creates_new_preferences(self) -> None:
        returned_prefs = MagicMock()
        returned_prefs.scoring_weights = {
            "lien_to_value": 50,
            "redemption_urgency": 20,
            "owner_motivation": 15,
            "contact_reachability": 15,
        }
        returned_prefs.api_keys = {"google_maps": "AIza-test"}

        mock_repo = AsyncMock()
        mock_repo.upsert.return_value = returned_prefs

        app = _make_test_app(mock_repo)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/settings/preferences",
                json={
                    "scoring_weights": {
                        "lien_to_value": 50,
                        "redemption_urgency": 20,
                        "owner_motivation": 15,
                        "contact_reachability": 15,
                    },
                    "api_keys": {"google_maps": "AIza-test"},
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["scoring_weights"]["lien_to_value"] == 50
        assert data["api_keys"]["google_maps"] == "AIza-test"
        mock_repo.upsert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_updates_only_scoring_weights(self) -> None:
        returned_prefs = MagicMock()
        returned_prefs.scoring_weights = {
            "lien_to_value": 30,
            "redemption_urgency": 30,
            "owner_motivation": 20,
            "contact_reachability": 20,
        }
        returned_prefs.api_keys = {}

        mock_repo = AsyncMock()
        mock_repo.upsert.return_value = returned_prefs

        app = _make_test_app(mock_repo)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/settings/preferences",
                json={
                    "scoring_weights": {
                        "lien_to_value": 30,
                        "redemption_urgency": 30,
                        "owner_motivation": 20,
                        "contact_reachability": 20,
                    },
                },
            )

        assert resp.status_code == 200
        # api_keys should be None (not sent to repo)
        call_kwargs = mock_repo.upsert.call_args
        assert call_kwargs.kwargs["api_keys"] is None

    @pytest.mark.asyncio
    async def test_updates_only_api_keys(self) -> None:
        returned_prefs = MagicMock()
        returned_prefs.scoring_weights = {}
        returned_prefs.api_keys = {"google_maps": "AIza-new"}

        mock_repo = AsyncMock()
        mock_repo.upsert.return_value = returned_prefs

        app = _make_test_app(mock_repo)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/settings/preferences",
                json={
                    "api_keys": {"google_maps": "AIza-new"},
                },
            )

        assert resp.status_code == 200
        # scoring_weights should be None (not sent to repo)
        call_kwargs = mock_repo.upsert.call_args
        assert call_kwargs.kwargs["scoring_weights"] is None

    @pytest.mark.asyncio
    async def test_weight_out_of_range_422(self) -> None:
        mock_repo = AsyncMock()
        app = _make_test_app(mock_repo)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/settings/preferences",
                json={
                    "scoring_weights": {
                        "lien_to_value": 150,
                        "redemption_urgency": 25,
                        "owner_motivation": 25,
                        "contact_reachability": 25,
                    },
                },
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_include_screenshots_persisted(self) -> None:
        """include_screenshots is stored inside scoring_weights blob."""
        existing_prefs = MagicMock()
        existing_prefs.scoring_weights = {"lien_to_value": 30}

        returned_prefs = MagicMock()
        returned_prefs.scoring_weights = {
            "lien_to_value": 30,
            "include_screenshots": False,
        }
        returned_prefs.api_keys = {}

        mock_repo = AsyncMock()
        mock_repo.get_by_user_id.return_value = existing_prefs
        mock_repo.upsert.return_value = returned_prefs

        app = _make_test_app(mock_repo)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/settings/preferences",
                json={"include_screenshots": False},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["include_screenshots"] is False
