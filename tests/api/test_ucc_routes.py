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
# Search UCC Filings — Happy Paths
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
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/ucc/filings",
                    params={"debtor_name": "ACME LLC", "state": "FL"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["filings"]) == 1
        assert data["filings"][0]["filing_number"] == "UCC-2023-001"

    @pytest.mark.asyncio
    async def test_search_by_state_filters_results(self) -> None:
        """Search filtered by state returns only matching filings."""
        mock = _mock_server()
        mock.search_ucc_filings.return_value = {
            "filings": [
                {
                    "filing_number": "UCC-TX-001",
                    "debtor_name": "Lone Star Corp",
                    "state": "TX",
                },
            ],
        }

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/ucc/filings",
                    params={"debtor_name": "Lone Star Corp", "state": "TX"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["filings"]) == 1
        assert data["filings"][0]["state"] == "TX"
        mock.search_ucc_filings.assert_called_once_with(
            debtor_name="Lone Star Corp", state="TX", filing_type=None
        )

    @pytest.mark.asyncio
    async def test_with_filing_type(self) -> None:
        mock = _mock_server()
        mock.search_ucc_filings.return_value = {"filings": []}

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
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
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/ucc/filings")

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        """Empty result set returns 200 with empty filings list."""
        mock = _mock_server()
        mock.search_ucc_filings.return_value = {"filings": []}

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/ucc/filings",
                    params={"debtor_name": "Nobody", "state": "AK"},
                )

        assert resp.status_code == 200
        assert resp.json()["filings"] == []

    @pytest.mark.asyncio
    async def test_result_limit_applied(self) -> None:
        """The limit parameter caps how many filings are returned."""
        mock = _mock_server()
        mock.search_ucc_filings.return_value = {
            "filings": [
                {"filing_number": f"UCC-{i:03d}", "state": "FL"}
                for i in range(50)
            ],
        }

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/ucc/filings",
                    params={
                        "debtor_name": "ACME",
                        "state": "FL",
                        "limit": 5,
                    },
                )

        assert resp.status_code == 200
        assert len(resp.json()["filings"]) == 5


# ═══════════════════════════════════════════════════════════════════════════════
# Search UCC Filings — Input Validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestSearchValidation:
    @pytest.mark.asyncio
    async def test_empty_debtor_name_rejected(self) -> None:
        """Empty debtor_name violates min_length=1 and returns 422."""
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/ucc/filings",
                params={"debtor_name": "", "state": "FL"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_oversized_debtor_name_rejected(self) -> None:
        """debtor_name exceeding 200 chars returns 422."""
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/ucc/filings",
                params={"debtor_name": "A" * 201, "state": "FL"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_state_code_too_short_rejected(self) -> None:
        """Single-character state code returns 422."""
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/ucc/filings",
                params={"debtor_name": "Test", "state": "F"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_state_code_too_long_rejected(self) -> None:
        """Three-character state code returns 422."""
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/ucc/filings",
                params={"debtor_name": "Test", "state": "FLA"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_lowercase_state_code_rejected(self) -> None:
        """Lowercase state code fails the ^[A-Z]{2}$ pattern."""
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/ucc/filings",
                params={"debtor_name": "Test", "state": "fl"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_numeric_state_code_rejected(self) -> None:
        """Numeric state code fails the ^[A-Z]{2}$ pattern."""
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/ucc/filings",
                params={"debtor_name": "Test", "state": "12"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_result_limit_below_minimum_rejected(self) -> None:
        """limit=0 violates ge=1 and returns 422."""
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/ucc/filings",
                params={
                    "debtor_name": "Test",
                    "state": "FL",
                    "limit": 0,
                },
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_result_limit_above_maximum_rejected(self) -> None:
        """limit=1001 violates le=1000 and returns 422."""
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/ucc/filings",
                params={
                    "debtor_name": "Test",
                    "state": "FL",
                    "limit": 1001,
                },
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_filing_type_too_long_rejected(self) -> None:
        """filing_type exceeding 50 chars returns 422."""
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/ucc/filings",
                params={
                    "debtor_name": "Test",
                    "state": "FL",
                    "filing_type": "x" * 51,
                },
            )

        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# Search UCC Filings — Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestSearchEdgeCases:
    @pytest.mark.asyncio
    async def test_sql_injection_attempt_handled_safely(self) -> None:
        """Special characters (SQL injection) are treated as literal text."""
        mock = _mock_server()
        mock.search_ucc_filings.return_value = {"filings": []}

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/ucc/filings",
                    params={
                        "debtor_name": "'; DROP TABLE filings;--",
                        "state": "FL",
                    },
                )

        assert resp.status_code == 200
        # The malicious string is passed through as literal text
        mock.search_ucc_filings.assert_called_once_with(
            debtor_name="'; DROP TABLE filings;--",
            state="FL",
            filing_type=None,
        )

    @pytest.mark.asyncio
    async def test_unicode_debtor_name_accepted(self) -> None:
        """Unicode characters in debtor name are accepted."""
        mock = _mock_server()
        mock.search_ucc_filings.return_value = {"filings": []}

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/ucc/filings",
                    params={
                        "debtor_name": "Muller GmbH",
                        "state": "NY",
                    },
                )

        assert resp.status_code == 200
        mock.search_ucc_filings.assert_called_once_with(
            debtor_name="Muller GmbH",
            state="NY",
            filing_type=None,
        )

    @pytest.mark.asyncio
    async def test_max_length_debtor_name_accepted(self) -> None:
        """A 200-character debtor_name (boundary) is accepted."""
        mock = _mock_server()
        mock.search_ucc_filings.return_value = {"filings": []}
        long_name = "A" * 200

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/ucc/filings",
                    params={"debtor_name": long_name, "state": "FL"},
                )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_special_characters_in_name(self) -> None:
        """Names with hyphens, ampersands, and periods are accepted."""
        mock = _mock_server()
        mock.search_ucc_filings.return_value = {"filings": []}

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/ucc/filings",
                    params={
                        "debtor_name": "Smith-Jones & Co., Inc.",
                        "state": "FL",
                    },
                )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_server_exception_returns_500(self) -> None:
        """Unhandled server exception surfaces as 500."""
        mock = _mock_server()
        mock.search_ucc_filings.side_effect = RuntimeError("unexpected")

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(
                app=app, raise_app_exceptions=False
            )
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/ucc/filings",
                    params={"debtor_name": "ACME", "state": "FL"},
                )

        assert resp.status_code == 500


# ═══════════════════════════════════════════════════════════════════════════════
# Get Filing Details — Happy Paths
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
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
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
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
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
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
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
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
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
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/ucc/filings/UCC-001")

        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# Get Filing Details — Input Validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestDetailValidation:
    @pytest.mark.asyncio
    async def test_lowercase_state_rejected(self) -> None:
        """Lowercase state code in detail endpoint returns 422."""
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/ucc/filings/UCC-001",
                params={"state": "fl"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_three_letter_state_rejected(self) -> None:
        """Three-letter state code in detail endpoint returns 422."""
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/ucc/filings/UCC-001",
                params={"state": "FLA"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_oversized_filing_number_rejected(self) -> None:
        """Filing number exceeding 50 chars returns 422."""
        long_number = "UCC-" + "0" * 50
        app = _make_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/v1/ucc/filings/{long_number}",
                params={"state": "FL"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_server_exception_returns_500(self) -> None:
        """Unhandled server exception in detail endpoint surfaces as 500."""
        mock = _mock_server()
        mock.get_filing_details.side_effect = RuntimeError("db crash")

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(
                app=app, raise_app_exceptions=False
            )
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/ucc/filings/UCC-001",
                    params={"state": "FL"},
                )

        assert resp.status_code == 500


# ═══════════════════════════════════════════════════════════════════════════════
# Authentication
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuth:
    @pytest.mark.asyncio
    async def test_unauthenticated_request_succeeds(self) -> None:
        """Requests without a token still succeed (auth is optional)."""
        mock = _mock_server()
        mock.search_ucc_filings.return_value = {"filings": []}

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/ucc/filings",
                    params={"debtor_name": "Test", "state": "FL"},
                )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_bearer_token_returns_401(self) -> None:
        """An invalid bearer token triggers 401 from get_current_user."""
        mock = _mock_server()
        mock.search_ucc_filings.return_value = {"filings": []}

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/ucc/filings",
                    params={"debtor_name": "Test", "state": "FL"},
                    headers={"Authorization": "Bearer invalid-token-xyz"},
                )

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_on_detail_returns_401(self) -> None:
        """An invalid bearer token on the detail endpoint triggers 401."""
        mock = _mock_server()
        mock.get_filing_details.return_value = {
            "filing_number": "UCC-001",
            "state": "FL",
        }

        app = _make_test_app()
        with patch.object(ucc_mod, "_get_server", return_value=mock):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/ucc/filings/UCC-001",
                    params={"state": "FL"},
                    headers={"Authorization": "Bearer bad-jwt"},
                )

        assert resp.status_code == 401
