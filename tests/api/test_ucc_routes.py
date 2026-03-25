"""Tests for UCC filing API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from aloha.api.routes import ucc as ucc_mod


def _make_test_app():
    """Build a minimal FastAPI app with just the UCC router."""
    from fastapi import FastAPI
    from aloha.api.routes.ucc import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


def _mock_server():
    """Create a mock UCCMCPServer."""
    server = MagicMock()
    server.search_ucc_filings = AsyncMock()
    server.get_filing_details = AsyncMock()
    return server


@pytest.fixture(autouse=True)
def _reset_server_singleton():
    """Reset the module-level server singleton between tests."""
    ucc_mod._server = None
    yield
    ucc_mod._server = None


# ═══════════════════════════════════════════════════════════════════════════════
# Search UCC Filings
# ═══════════════════════════════════════════════════════════════════════════════


class TestSearchUCCFilings:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        mock = _mock_server()
        mock.search_ucc_filings.return_value = {
            "filings": [
                {
                    "filing_number": "UCC-2023-001",
                    "filing_date": "2023-01-15",
                    "debtor_name": "ACME LLC",
                    "secured_party": "First National Bank",
                    "collateral": "All assets",
                    "state": "FL",
                },
            ],
        }

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/ucc/filings",
                    params={"debtor_name": "ACME LLC", "state": "FL"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["filings"]) == 1
        assert data["filings"][0]["filing_number"] == "UCC-2023-001"

    @pytest.mark.asyncio
    async def test_with_filing_type(self) -> None:
        mock = _mock_server()
        mock.search_ucc_filings.return_value = {"filings": []}

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/ucc/filings",
                    params={
                        "debtor_name": "Corp",
                        "state": "TX",
                        "filing_type": "initial",
                    },
                )

        assert resp.status_code == 200
        mock.search_ucc_filings.assert_called_once_with(
            debtor_name="Corp", state="TX", filing_type="initial"
        )

    @pytest.mark.asyncio
    async def test_missing_required_params(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/ucc/filings")

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        mock = _mock_server()
        mock.search_ucc_filings.return_value = {"filings": []}

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/ucc/filings",
                    params={"debtor_name": "Nobody", "state": "AK"},
                )

        assert resp.status_code == 200
        assert resp.json()["filings"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# Get Filing Details
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetFilingDetails:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        mock = _mock_server()
        mock.get_filing_details.return_value = {
            "filing_number": "UCC-2023-001",
            "filing_date": "2023-01-15",
            "lapse_date": "2028-01-15",
            "debtor_name": "ACME LLC",
            "secured_party": "First National Bank",
            "collateral": "All inventory and equipment",
            "state": "FL",
        }

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/ucc/filings/UCC-2023-001",
                    params={"state": "FL"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["filing_number"] == "UCC-2023-001"
        assert data["lapse_date"] == "2028-01-15"
        assert data["collateral"] == "All inventory and equipment"

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self) -> None:
        mock = _mock_server()
        mock.get_filing_details.return_value = {
            "error": "Filing FAKE-001 not found in FL"
        }

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/ucc/filings/FAKE-001",
                    params={"state": "FL"},
                )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_not_configured_returns_503(self) -> None:
        mock = _mock_server()
        mock.get_filing_details.return_value = {
            "error": "Cobalt Intelligence API key not configured"
        }

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/ucc/filings/UCC-001",
                    params={"state": "FL"},
                )

        assert resp.status_code == 503
        assert "not configured" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upstream_error_returns_502(self) -> None:
        mock = _mock_server()
        mock.get_filing_details.return_value = {"error": "API error 500"}

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/ucc/filings/UCC-001",
                    params={"state": "FL"},
                )

        assert resp.status_code == 502
        assert "API error 500" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_missing_state_param(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/ucc/filings/UCC-001")

        assert resp.status_code == 422
