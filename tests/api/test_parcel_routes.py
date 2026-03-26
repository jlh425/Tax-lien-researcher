"""Tests for parcel API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from aloha.api.deps import get_current_user
from aloha.api.routes.parcels import _parcel_service


def _make_test_app(mock_svc=None):
    """Build a minimal FastAPI app with the parcels router and overridden deps."""
    from fastapi import FastAPI

    from aloha.api.routes.parcels import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: None
    if mock_svc is not None:
        app.dependency_overrides[_parcel_service] = lambda: mock_svc
    return app


def _summary_obj(**overrides):
    """Build a mock ParcelSummary-compatible object."""
    defaults = {
        "parcel_id": "P001",
        "state": "FL",
        "county": "orange",
        "address": "123 Main St",
        "property_type": "residential",
        "zoning": "R-1",
        "acreage": 0.25,
        "assessed_total": 150000,
        "research_status": "scored",
        "data_freshness": "current",
        "latitude": 28.54,
        "longitude": -81.38,
        "instrument_type": "lien_certificate",
        "lien_status": "active",
        "total_owed": 5000.0,
        "redemption_deadline": None,
        "auction_date": None,
        "overall_score": 85,
        "risk_flags": [],
    }
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _detail_obj(**overrides):
    """Build a mock ParcelDetail-compatible object."""
    now = datetime.now(tz=timezone.utc)
    defaults = {
        "parcel_id": "P001",
        "user_id": None,
        "state": "FL",
        "county": "orange",
        "address": "123 Main St",
        "address_normalized": None,
        "legal_description": None,
        "acreage": 0.25,
        "land_use_code": None,
        "property_type": "residential",
        "zoning": "R-1",
        "zoning_notes": None,
        "assessed_land_val": 50000,
        "assessed_impr_val": 100000,
        "assessed_total": 150000,
        "market_value_est": 200000,
        "last_sale_date": None,
        "last_sale_price": None,
        "year_built": 1990,
        "latitude": 28.54,
        "longitude": -81.38,
        "research_status": "scored",
        "data_freshness": "current",
        "last_crawled_at": None,
        "created_at": now,
        "updated_at": now,
        "tax_liens": [],
        "owners": [],
        "scores": [],
        "images": [],
        "condition_summary": None,
    }
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


class TestListParcels:
    @pytest.mark.asyncio
    async def test_list_parcels_success(self) -> None:
        mock_svc = AsyncMock()
        mock_svc.list_parcels.return_value = [_summary_obj()]

        app = _make_test_app(mock_svc)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/parcels?state=FL&county=orange")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["parcel_id"] == "P001"

    @pytest.mark.asyncio
    async def test_list_parcels_with_filters(self) -> None:
        mock_svc = AsyncMock()
        mock_svc.list_parcels.return_value = []

        app = _make_test_app(mock_svc)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/parcels",
                params={
                    "state": "FL",
                    "min_score": 80,
                    "instrument_type": "tax_deed",
                    "limit": 10,
                },
            )
        assert resp.status_code == 200
        mock_svc.list_parcels.assert_awaited_once()
        call_kwargs = mock_svc.list_parcels.call_args.kwargs
        assert call_kwargs["state"] == "FL"
        assert call_kwargs["min_score"] == 80
        assert call_kwargs["limit"] == 10

    @pytest.mark.asyncio
    async def test_list_parcels_invalid_min_score(self) -> None:
        app = _make_test_app(AsyncMock())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/parcels?min_score=200")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_parcels_empty(self) -> None:
        mock_svc = AsyncMock()
        mock_svc.list_parcels.return_value = []

        app = _make_test_app(mock_svc)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/parcels")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetParcel:
    @pytest.mark.asyncio
    async def test_get_parcel_success(self) -> None:
        mock_svc = AsyncMock()
        mock_svc.get_parcel_detail.return_value = _detail_obj()

        app = _make_test_app(mock_svc)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/parcels/P001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["parcel_id"] == "P001"
        assert data["assessed_total"] == 150000

    @pytest.mark.asyncio
    async def test_get_parcel_not_found(self) -> None:
        from fastapi import HTTPException

        mock_svc = AsyncMock()
        mock_svc.get_parcel_detail.side_effect = HTTPException(
            status_code=404, detail="Parcel not found"
        )

        app = _make_test_app(mock_svc)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/parcels/NONEXISTENT")
        assert resp.status_code == 404
