"""Tests for the Court Records MCP Server."""

from __future__ import annotations

import pytest

from aloha.mcp_servers.court_records.server import (
    CourtRecordsMCPServer,
    _normalise_case,
    _normalise_lien,
    create_court_records_server,
)


# -- Init & Tool Registration -------------------------------------------------

class TestInit:
    def test_server_name(self) -> None:
        server = CourtRecordsMCPServer()
        assert server.name == "court_records"

    def test_tools_registered(self) -> None:
        server = CourtRecordsMCPServer()
        assert "search_federal_cases" in server.tools
        assert "search_state_liens" in server.tools
        assert "get_case_details" in server.tools

    def test_tool_count(self) -> None:
        server = CourtRecordsMCPServer()
        assert len(server.tools) == 3

    def test_tool_schemas_have_required_fields(self) -> None:
        server = CourtRecordsMCPServer()
        schema = server.tools["search_federal_cases"].input_schema
        assert "party_name" in schema["properties"]
        assert "party_name" in schema["required"]


# -- Stub Success Paths --------------------------------------------------------

class TestSuccessPaths:
    @pytest.mark.asyncio
    async def test_search_federal_cases_returns_stub(self) -> None:
        server = CourtRecordsMCPServer()
        result = await server.search_federal_cases(party_name="Doe")
        assert result["stub"] is True
        assert result["cases"] == []
        assert result["query"]["party_name"] == "Doe"

    @pytest.mark.asyncio
    async def test_search_federal_cases_with_optional_params(self) -> None:
        server = CourtRecordsMCPServer()
        result = await server.search_federal_cases(
            party_name="Smith", state="FL", case_type="civil"
        )
        assert result["query"]["state"] == "FL"
        assert result["query"]["case_type"] == "civil"

    @pytest.mark.asyncio
    async def test_search_state_liens_returns_stub(self) -> None:
        server = CourtRecordsMCPServer()
        result = await server.search_state_liens(debtor_name="Doe", state="TX")
        assert result["stub"] is True
        assert result["liens"] == []
        assert result["query"]["debtor_name"] == "Doe"
        assert result["query"]["state"] == "TX"

    @pytest.mark.asyncio
    async def test_search_state_liens_with_lien_type(self) -> None:
        server = CourtRecordsMCPServer()
        result = await server.search_state_liens(
            debtor_name="Smith", state="GA", lien_type="tax"
        )
        assert result["query"]["lien_type"] == "tax"

    @pytest.mark.asyncio
    async def test_get_case_details_returns_stub(self) -> None:
        server = CourtRecordsMCPServer()
        result = await server.get_case_details(case_id="CASE-123")
        assert result["stub"] is True
        assert result["case_id"] == "CASE-123"
        assert result["detail"] is None

    @pytest.mark.asyncio
    async def test_handle_call_dispatches(self) -> None:
        server = CourtRecordsMCPServer()
        result = await server.handle_call(
            "search_federal_cases", {"party_name": "Test"}
        )
        assert result["stub"] is True


# -- Error Paths ---------------------------------------------------------------

class TestErrorPaths:
    @pytest.mark.asyncio
    async def test_unknown_tool_raises_key_error(self) -> None:
        server = CourtRecordsMCPServer()
        with pytest.raises(KeyError, match="not_a_tool"):
            await server.handle_call("not_a_tool", {})


# -- Normalisation Helpers -----------------------------------------------------

class TestNormalisation:
    def test_normalise_case_maps_fields(self) -> None:
        raw = {
            "id": "C-1",
            "title": "Doe v. State",
            "court_name": "USDC-SDFL",
            "type": "civil",
            "filed_date": "2024-01-15",
            "case_status": "open",
            "parties": [{"name": "Doe", "role": "plaintiff"}],
        }
        result = _normalise_case(raw)
        assert result["case_id"] == "C-1"
        assert result["case_title"] == "Doe v. State"
        assert result["court"] == "USDC-SDFL"
        assert result["case_type"] == "civil"
        assert result["filing_date"] == "2024-01-15"
        assert result["status"] == "open"
        assert len(result["parties"]) == 1

    def test_normalise_case_prefers_primary_keys(self) -> None:
        raw = {"case_id": "C-2", "id": "C-3", "case_title": "A", "title": "B"}
        result = _normalise_case(raw)
        assert result["case_id"] == "C-2"
        assert result["case_title"] == "A"

    def test_normalise_case_handles_missing(self) -> None:
        result = _normalise_case({})
        assert result["case_id"] is None
        assert result["parties"] == []

    def test_normalise_lien_maps_fields(self) -> None:
        raw = {
            "instrument_number": "L-100",
            "debtor_name": "Jane Doe",
            "creditor_name": "IRS",
            "lien_amount": 50000,
            "recorded_date": "2023-06-01",
            "state": "FL",
        }
        result = _normalise_lien(raw)
        assert result["filing_number"] == "L-100"
        assert result["debtor"] == "Jane Doe"
        assert result["creditor"] == "IRS"
        assert result["amount"] == 50000
        assert result["filing_date"] == "2023-06-01"
        assert result["state"] == "FL"

    def test_normalise_lien_prefers_primary_keys(self) -> None:
        raw = {"filing_number": "F-1", "instrument_number": "F-2"}
        result = _normalise_lien(raw)
        assert result["filing_number"] == "F-1"


# -- Factory -------------------------------------------------------------------

class TestFactory:
    def test_create_court_records_server(self) -> None:
        server = create_court_records_server()
        assert isinstance(server, CourtRecordsMCPServer)
        assert server.name == "court_records"

    def test_factory_returns_working_server(self) -> None:
        server = create_court_records_server()
        assert len(server.tools) == 3
