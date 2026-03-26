"""Tests for scan / queue API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from aloha.api.deps import get_current_user
from aloha.api.routes.scan import _research_service


def _fake_user():
    """Return a mock user object for auth override."""
    u = MagicMock()
    u.id = "user-test-123"
    u.tier = "free"
    return u


def _make_test_app(mock_svc=None):
    """Build a minimal FastAPI app with the scan router and overridden deps."""
    from fastapi import FastAPI

    from aloha.api.routes.scan import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    # Override auth to return a mock user (routes access user.id and user.tier)
    app.dependency_overrides[get_current_user] = _fake_user
    if mock_svc is not None:
        app.dependency_overrides[_research_service] = lambda: mock_svc
    return app


class TestTriggerScan:
    @pytest.mark.asyncio
    async def test_trigger_scan_success(self) -> None:
        from aloha.api.schemas.parcels import ScanResponse

        mock_svc = AsyncMock()
        mock_svc.trigger_scan.return_value = ScanResponse(
            status="queued",
            state="FL",
            county="orange",
            records_found=0,
            enqueued=0,
            message="Scan queued",
        )

        app = _make_test_app(mock_svc)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("aloha.api.routes.scan._run_discovery", new_callable=AsyncMock):
                resp = await client.post(
                    "/api/v1/run",
                    json={"state": "FL", "county": "orange"},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "queued"
        assert data["state"] == "FL"

    @pytest.mark.asyncio
    async def test_trigger_scan_state_too_long_422(self) -> None:
        app = _make_test_app(AsyncMock())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/run",
                json={"state": "TOOLONG", "county": "orange"},
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_trigger_scan_missing_county_422(self) -> None:
        app = _make_test_app(AsyncMock())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/run",
                json={"state": "FL"},
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_trigger_scan_quota_exceeded(self) -> None:
        from fastapi import HTTPException

        mock_svc = AsyncMock()
        mock_svc.trigger_scan.side_effect = HTTPException(
            status_code=429, detail="Monthly scan quota exceeded"
        )

        app = _make_test_app(mock_svc)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("aloha.api.routes.scan._run_discovery", new_callable=AsyncMock):
                resp = await client.post(
                    "/api/v1/run",
                    json={"state": "FL", "county": "orange"},
                )
        assert resp.status_code == 429


class TestQueueStatus:
    @pytest.mark.asyncio
    async def test_queue_status_success(self) -> None:
        from aloha.api.schemas.parcels import QueueStatusOut

        mock_svc = AsyncMock()
        mock_svc.get_queue_status.return_value = QueueStatusOut(
            pending=5,
            processing=2,
            failed=1,
            complete=10,
            agents={"discover": 3},
        )

        app = _make_test_app(mock_svc)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/queue/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending"] == 5
        assert data["complete"] == 10
        assert data["agents"]["discover"] == 3
