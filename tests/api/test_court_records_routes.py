"""Tests for court records API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from aloha.api.routes import court_records as court_records_mod


def _make_test_app():
    """Build a minimal FastAPI app with just the court records router."""
    from fastapi import FastAPI
    from aloha.api.routes.court_records import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


def _mock_server():
    """Create a mock CourtRecordsMCPServer."""
    server = MagicMock()
    server.search_federal_cases = AsyncMock()
    server.get_case_details = AsyncMock()
    server.search_state_liens = AsyncMock()
    return server


@pytest.fixture(autouse=True)
def _reset_server_singleton():
    """Reset the module-level server singleton between tests."""
    court_records_mod._server = None
    yield
    court_records_mod._server = None


# ═══════════════════════════════════════════════════════════════════════════════
# Search Federal Cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestSearchFederalCases:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        mock = _mock_server()
        mock.search_federal_cases.return_value = {
            "cases": [
                {
                    "case_id": "123",
                    "case_title": "Smith v. Jones",
                    "court": "flsd",
                    "filing_date": "2023-01-15",
                    "status": "Open",
                    "parties": [],
                    "docket_url": "/docket/123/",
                },
            ],
        }

        app = _make_test_app()
        with patch.object(court_records_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/court-records/cases", params={"party_name": "Smith"}
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["cases"]) == 1
        assert data["cases"][0]["case_id"] == "123"
        assert data["cases"][0]["case_title"] == "Smith v. Jones"

    @pytest.mark.asyncio
    async def test_with_filters(self) -> None:
        mock = _mock_server()
        mock.search_federal_cases.return_value = {"cases": []}

        app = _make_test_app()
        with patch.object(court_records_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/court-records/cases",
                    params={"party_name": "Doe", "state": "FL", "case_type": "civil"},
                )

        assert resp.status_code == 200
        mock.search_federal_cases.assert_called_once_with(
            party_name="Doe", state="FL", case_type="civil"
        )

    @pytest.mark.asyncio
    async def test_missing_party_name(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/court-records/cases")

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_error_inline(self) -> None:
        """Search endpoints return 200 with error field (cascade may have partial results)."""
        mock = _mock_server()
        mock.search_federal_cases.return_value = {
            "error": "API error 403",
            "cases": [],
        }

        app = _make_test_app()
        with patch.object(court_records_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/court-records/cases", params={"party_name": "Smith"}
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] == "API error 403"
        assert data["cases"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# Get Case Details
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetCaseDetails:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        mock = _mock_server()
        mock.get_case_details.return_value = {
            "case_id": "123",
            "case_title": "Smith v. Jones",
            "court": "flsd",
            "filing_date": "2023-01-15",
            "status": "Open",
            "parties": [{"name": "Smith", "role": "Plaintiff"}],
            "docket_url": "/docket/123/",
        }

        app = _make_test_app()
        with patch.object(court_records_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/court-records/cases/123")

        assert resp.status_code == 200
        data = resp.json()
        assert data["case_id"] == "123"
        assert len(data["parties"]) == 1

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self) -> None:
        mock = _mock_server()
        mock.get_case_details.return_value = {"error": "Docket 99999 not found"}

        app = _make_test_app()
        with patch.object(court_records_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/court-records/cases/99999")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_not_configured_returns_503(self) -> None:
        mock = _mock_server()
        mock.get_case_details.return_value = {
            "error": "CourtListener API key not configured"
        }

        app = _make_test_app()
        with patch.object(court_records_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/court-records/cases/123")

        assert resp.status_code == 503
        assert "not configured" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upstream_error_returns_502(self) -> None:
        mock = _mock_server()
        mock.get_case_details.return_value = {"error": "API error 500"}

        app = _make_test_app()
        with patch.object(court_records_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/court-records/cases/123")

        assert resp.status_code == 502
        assert "API error 500" in resp.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════════════
# Search State Liens
# ═══════════════════════════════════════════════════════════════════════════════


class TestSearchStateLiens:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        mock = _mock_server()
        mock.search_state_liens.return_value = {
            "liens": [
                {
                    "filing_number": "LN-001",
                    "debtor": "ACME LLC",
                    "creditor": "IRS",
                    "amount": 50000,
                    "filing_date": "2023-06-01",
                    "lien_type": "tax",
                    "state": "FL",
                },
            ],
        }

        app = _make_test_app()
        with patch.object(court_records_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/court-records/liens",
                    params={"debtor_name": "ACME LLC", "state": "FL"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["liens"]) == 1
        assert data["liens"][0]["debtor"] == "ACME LLC"

    @pytest.mark.asyncio
    async def test_missing_required_params(self) -> None:
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/court-records/liens")

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_with_lien_type_filter(self) -> None:
        mock = _mock_server()
        mock.search_state_liens.return_value = {"liens": []}

        app = _make_test_app()
        with patch.object(court_records_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/court-records/liens",
                    params={"debtor_name": "Doe", "state": "TX", "lien_type": "tax"},
                )

        assert resp.status_code == 200
        mock.search_state_liens.assert_called_once_with(
            debtor_name="Doe", state="TX", lien_type="tax"
        )
