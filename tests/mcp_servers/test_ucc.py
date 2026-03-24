"""Tests for the UCC Filing MCP Server."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aloha.mcp_servers.ucc.server import (
    UCCMCPServer,
    _normalise_ucc_filing,
    create_ucc_server,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Init & Tool Registration
# ═══════════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_server_name(self) -> None:
        server = UCCMCPServer(cobalt_api_key="fake-key")
        assert server.name == "ucc"

    def test_tools_registered(self) -> None:
        server = UCCMCPServer(cobalt_api_key="fake-key")
        assert "search_ucc_filings" in server.tools
        assert "get_filing_details" in server.tools

    def test_tool_count(self) -> None:
        server = UCCMCPServer(cobalt_api_key="fake-key")
        assert len(server.tools) == 2

    def test_provider_set_with_key(self) -> None:
        server = UCCMCPServer(cobalt_api_key="fake-key")
        assert server._provider is not None

    def test_provider_none_without_key(self) -> None:
        server = UCCMCPServer()
        assert server._provider is None

    def test_scraper_always_set(self) -> None:
        server = UCCMCPServer()
        assert server._scraper is not None

    def test_search_schema_requires_debtor_and_state(self) -> None:
        server = UCCMCPServer()
        schema = server.tools["search_ucc_filings"].input_schema
        assert "debtor_name" in schema["required"]
        assert "state" in schema["required"]

    def test_details_schema_requires_filing_number_and_state(self) -> None:
        server = UCCMCPServer()
        schema = server.tools["get_filing_details"].input_schema
        assert "filing_number" in schema["required"]
        assert "state" in schema["required"]


# ═══════════════════════════════════════════════════════════════════════════════
# Success Paths (mocked providers)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSuccessPaths:
    @pytest.mark.asyncio
    async def test_search_ucc_filings(self) -> None:
        server = UCCMCPServer(cobalt_api_key="fake-key")
        server._provider = MagicMock()
        server._provider.search = AsyncMock(return_value=[
            {
                "filing_number": "UCC-2023-001",
                "filing_date": "2023-01-15",
                "debtor_name": "ACME LLC",
                "secured_party": "First National Bank",
                "collateral": "All assets",
                "state": "FL",
            },
        ])

        result = await server.search_ucc_filings("ACME LLC", "FL")

        assert len(result["filings"]) == 1
        assert result["filings"][0]["filing_number"] == "UCC-2023-001"
        assert result["filings"][0]["debtor_name"] == "ACME LLC"
        assert result["filings"][0]["secured_party"] == "First National Bank"

    @pytest.mark.asyncio
    async def test_search_with_filing_type(self) -> None:
        server = UCCMCPServer(cobalt_api_key="fake-key")
        server._provider = MagicMock()
        server._provider.search = AsyncMock(return_value=[])

        await server.search_ucc_filings("ACME", "FL", filing_type="initial")

        server._provider.search.assert_called_once_with(
            debtor_name="ACME", state="FL", filing_type="initial"
        )

    @pytest.mark.asyncio
    async def test_search_scraper_fallback(self) -> None:
        """Scraper runs even when Cobalt has results."""
        server = UCCMCPServer(cobalt_api_key="fake-key")
        server._provider = MagicMock()
        server._provider.search = AsyncMock(return_value=[])
        server._scraper.search = AsyncMock(return_value=[
            {"debtor": "ACME LLC", "secured_party": "Bank B", "state": "FL"},
        ])

        result = await server.search_ucc_filings("ACME LLC", "FL")

        assert len(result["filings"]) == 1
        assert result["filings"][0]["secured_party"] == "Bank B"

    @pytest.mark.asyncio
    async def test_search_no_api_key(self) -> None:
        """Without API key, only scraper is used."""
        server = UCCMCPServer()
        server._scraper.search = AsyncMock(return_value=[])

        result = await server.search_ucc_filings("ACME LLC", "FL")

        assert result["filings"] == []

    @pytest.mark.asyncio
    async def test_get_filing_details(self) -> None:
        server = UCCMCPServer(cobalt_api_key="fake-key")
        server._provider = MagicMock()
        server._provider.get_detail = AsyncMock(return_value={
            "filing_number": "UCC-2023-001",
            "filing_date": "2023-01-15",
            "lapse_date": "2028-01-15",
            "debtor_name": "ACME LLC",
            "secured_party": "First National Bank",
            "collateral": "All inventory and equipment",
            "state": "FL",
        })

        result = await server.get_filing_details("UCC-2023-001", "FL")

        assert result["filing_number"] == "UCC-2023-001"
        assert result["lapse_date"] == "2028-01-15"
        assert result["collateral"] == "All inventory and equipment"

    @pytest.mark.asyncio
    async def test_get_filing_details_not_found(self) -> None:
        server = UCCMCPServer(cobalt_api_key="fake-key")
        server._provider = MagicMock()
        server._provider.get_detail = AsyncMock(return_value=None)

        result = await server.get_filing_details("FAKE-001", "FL")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_handle_call_dispatches(self) -> None:
        server = UCCMCPServer()
        result = await server.handle_call(
            "search_ucc_filings", {"debtor_name": "Test", "state": "CA"}
        )
        # Without API key, scraper-only mode — returns filings list
        assert "filings" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Error Paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorPaths:
    @pytest.mark.asyncio
    async def test_details_no_api_key(self) -> None:
        server = UCCMCPServer()

        result = await server.get_filing_details("UCC-001", "FL")

        assert "error" in result
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_details_http_error(self) -> None:
        server = UCCMCPServer(cobalt_api_key="fake-key")
        resp = MagicMock()
        resp.status_code = 404
        server._provider = MagicMock()
        server._provider.get_detail = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "not found", request=MagicMock(), response=resp
            )
        )

        result = await server.get_filing_details("FAKE-001", "FL")

        assert "error" in result
        assert "404" in result["error"]

    @pytest.mark.asyncio
    async def test_details_generic_exception(self) -> None:
        server = UCCMCPServer(cobalt_api_key="fake-key")
        server._provider = MagicMock()
        server._provider.get_detail = AsyncMock(
            side_effect=RuntimeError("timeout")
        )

        result = await server.get_filing_details("UCC-001", "FL")

        assert "error" in result
        assert "timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_search_cobalt_error_still_runs_scraper(self) -> None:
        """Cobalt error doesn't prevent scraper from running."""
        server = UCCMCPServer(cobalt_api_key="fake-key")
        resp = MagicMock()
        resp.status_code = 500
        server._provider = MagicMock()
        server._provider.search = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "server error", request=MagicMock(), response=resp
            )
        )
        server._scraper.search = AsyncMock(return_value=[])

        result = await server.search_ucc_filings("ACME", "FL")

        assert "filings" in result
        server._scraper.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_cobalt_generic_error_still_runs_scraper(self) -> None:
        """Generic Cobalt error doesn't prevent scraper from running."""
        server = UCCMCPServer(cobalt_api_key="fake-key")
        server._provider = MagicMock()
        server._provider.search = AsyncMock(
            side_effect=ConnectionError("refused")
        )
        server._scraper.search = AsyncMock(return_value=[])

        result = await server.search_ucc_filings("ACME", "FL")

        assert "filings" in result
        server._scraper.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_tool_raises_key_error(self) -> None:
        server = UCCMCPServer()
        with pytest.raises(KeyError, match="bogus"):
            await server.handle_call("bogus", {})


# ═══════════════════════════════════════════════════════════════════════════════
# Normalisation helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestNormalisation:
    def test_standard_fields(self) -> None:
        raw = {
            "filing_number": "UCC-001",
            "filing_date": "2023-01-15",
            "lapse_date": "2028-01-15",
            "filing_type": "initial",
            "debtor_name": "ACME LLC",
            "secured_party": "Big Bank",
            "collateral": "All assets",
            "state": "FL",
        }
        result = _normalise_ucc_filing(raw)
        assert result["filing_number"] == "UCC-001"
        assert result["filing_date"] == "2023-01-15"
        assert result["lapse_date"] == "2028-01-15"
        assert result["filing_type"] == "initial"
        assert result["debtor_name"] == "ACME LLC"
        assert result["secured_party"] == "Big Bank"
        assert result["collateral"] == "All assets"
        assert result["state"] == "FL"

    def test_alternate_field_names(self) -> None:
        raw = {
            "file_number": "UCC-002",
            "file_date": "2023-02-01",
            "expiration_date": "2028-02-01",
            "type": "amendment",
            "debtor": "XYZ Corp",
            "secured_party_name": "Small Bank",
            "collateral_description": "Equipment only",
            "state": "IL",
        }
        result = _normalise_ucc_filing(raw)
        assert result["filing_number"] == "UCC-002"
        assert result["filing_date"] == "2023-02-01"
        assert result["lapse_date"] == "2028-02-01"
        assert result["filing_type"] == "amendment"
        assert result["debtor_name"] == "XYZ Corp"
        assert result["secured_party"] == "Small Bank"
        assert result["collateral"] == "Equipment only"

    def test_prefers_primary_keys(self) -> None:
        raw = {
            "filing_number": "F-1",
            "file_number": "F-2",
            "filing_date": "2024-01-01",
            "file_date": "2024-02-01",
        }
        result = _normalise_ucc_filing(raw)
        assert result["filing_number"] == "F-1"
        assert result["filing_date"] == "2024-01-01"

    def test_empty_raw(self) -> None:
        result = _normalise_ucc_filing({})
        assert result["filing_number"] is None
        assert result["debtor_name"] is None
        assert result["secured_party"] is None
        assert result["collateral"] is None
        assert result["state"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════════════════════


class TestFactory:
    def test_with_api_key(self) -> None:
        with patch("aloha.config.settings") as mock_settings:
            mock_settings.cobalt_intelligence_api_key = "test-key-123"
            server = create_ucc_server()
            assert isinstance(server, UCCMCPServer)
            assert server._provider is not None

    def test_without_api_key(self) -> None:
        """Should still create server (graceful degradation / scraper-only mode)."""
        with patch("aloha.config.settings") as mock_settings:
            mock_settings.cobalt_intelligence_api_key = None
            server = create_ucc_server()
            assert isinstance(server, UCCMCPServer)
            assert server._provider is None
