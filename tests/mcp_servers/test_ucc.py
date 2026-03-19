"""Tests for the UCC Filing MCP Server."""

from __future__ import annotations

import pytest

from aloha.mcp_servers.ucc.server import (
    UCCMCPServer,
    _normalise_ucc_filing,
    create_ucc_server,
)


# -- Init & Tool Registration -------------------------------------------------

class TestInit:
    def test_server_name(self) -> None:
        server = UCCMCPServer()
        assert server.name == "ucc"

    def test_tools_registered(self) -> None:
        server = UCCMCPServer()
        assert "search_ucc_filings" in server.tools
        assert "get_filing_details" in server.tools

    def test_tool_count(self) -> None:
        server = UCCMCPServer()
        assert len(server.tools) == 2

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


# -- Stub Success Paths --------------------------------------------------------

class TestSuccessPaths:
    @pytest.mark.asyncio
    async def test_search_ucc_filings_returns_stub(self) -> None:
        server = UCCMCPServer()
        result = await server.search_ucc_filings(debtor_name="Acme LLC", state="FL")
        assert result["stub"] is True
        assert result["filings"] == []
        assert result["query"]["debtor_name"] == "Acme LLC"
        assert result["query"]["state"] == "FL"

    @pytest.mark.asyncio
    async def test_search_with_filing_type(self) -> None:
        server = UCCMCPServer()
        result = await server.search_ucc_filings(
            debtor_name="Corp", state="TX", filing_type="initial"
        )
        assert result["query"]["filing_type"] == "initial"

    @pytest.mark.asyncio
    async def test_get_filing_details_returns_stub(self) -> None:
        server = UCCMCPServer()
        result = await server.get_filing_details(
            filing_number="UCC-2024-001", state="GA"
        )
        assert result["stub"] is True
        assert result["filing_number"] == "UCC-2024-001"
        assert result["state"] == "GA"
        assert result["detail"] is None

    @pytest.mark.asyncio
    async def test_handle_call_dispatches(self) -> None:
        server = UCCMCPServer()
        result = await server.handle_call(
            "search_ucc_filings", {"debtor_name": "Test", "state": "CA"}
        )
        assert result["stub"] is True


# -- Error Paths ---------------------------------------------------------------

class TestErrorPaths:
    @pytest.mark.asyncio
    async def test_unknown_tool_raises_key_error(self) -> None:
        server = UCCMCPServer()
        with pytest.raises(KeyError, match="bogus"):
            await server.handle_call("bogus", {})


# -- Normalisation Helpers -----------------------------------------------------

class TestNormalisation:
    def test_normalise_ucc_filing_maps_fields(self) -> None:
        raw = {
            "file_number": "UCC-001",
            "file_date": "2024-03-01",
            "expiration_date": "2029-03-01",
            "debtor": "Acme LLC",
            "secured_party_name": "Big Bank",
            "collateral_description": "All assets",
        }
        result = _normalise_ucc_filing(raw)
        assert result["filing_number"] == "UCC-001"
        assert result["filing_date"] == "2024-03-01"
        assert result["lapse_date"] == "2029-03-01"
        assert result["debtor_name"] == "Acme LLC"
        assert result["secured_party"] == "Big Bank"
        assert result["collateral"] == "All assets"

    def test_normalise_prefers_primary_keys(self) -> None:
        raw = {
            "filing_number": "F-1",
            "file_number": "F-2",
            "filing_date": "2024-01-01",
            "file_date": "2024-02-01",
        }
        result = _normalise_ucc_filing(raw)
        assert result["filing_number"] == "F-1"
        assert result["filing_date"] == "2024-01-01"

    def test_normalise_handles_missing(self) -> None:
        result = _normalise_ucc_filing({})
        assert result["filing_number"] is None
        assert result["debtor_name"] is None
        assert result["collateral"] is None


# -- Factory -------------------------------------------------------------------

class TestFactory:
    def test_create_ucc_server(self) -> None:
        server = create_ucc_server()
        assert isinstance(server, UCCMCPServer)
        assert server.name == "ucc"

    def test_factory_returns_working_server(self) -> None:
        server = create_ucc_server()
        assert len(server.tools) == 2
