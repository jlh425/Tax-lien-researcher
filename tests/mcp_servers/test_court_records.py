"""Tests for the Court Records MCP Server."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aloha.mcp_servers.court_records.server import (
    CourtRecordsMCPServer,
    _normalise_case,
    _normalise_lien,
    create_court_records_server,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Init & Tool Registration
# ═══════════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_server_name(self) -> None:
        server = CourtRecordsMCPServer(courtlistener_api_key="fake-key")
        assert server.name == "court_records"

    def test_tools_registered(self) -> None:
        server = CourtRecordsMCPServer(courtlistener_api_key="fake-key")
        assert "search_federal_cases" in server.tools
        assert "search_state_liens" in server.tools
        assert "get_case_details" in server.tools

    def test_tool_count(self) -> None:
        server = CourtRecordsMCPServer(courtlistener_api_key="fake-key")
        assert len(server.tools) == 3

    def test_provider_set_with_key(self) -> None:
        server = CourtRecordsMCPServer(courtlistener_api_key="fake-key")
        assert server._provider is not None

    def test_provider_none_without_key(self) -> None:
        server = CourtRecordsMCPServer()
        assert server._provider is None

    def test_lien_scraper_always_set(self) -> None:
        server = CourtRecordsMCPServer()
        assert server._lien_scraper is not None

    def test_tool_schemas_have_required_fields(self) -> None:
        server = CourtRecordsMCPServer()
        schema = server.tools["search_federal_cases"].input_schema
        assert "party_name" in schema["properties"]
        assert "party_name" in schema["required"]


# ═══════════════════════════════════════════════════════════════════════════════
# Success Paths (mocked providers)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSuccessPaths:
    @pytest.mark.asyncio
    async def test_search_federal_cases(self) -> None:
        server = CourtRecordsMCPServer(courtlistener_api_key="fake-key")
        server._provider = MagicMock()
        server._provider.search = AsyncMock(return_value=[
            {
                "docket_id": 12345,
                "caseName": "Smith v. Jones",
                "court": "flsd",
                "dateFiled": "2023-01-15",
                "status": "Open",
            },
        ])

        result = await server.search_federal_cases("Smith")

        assert len(result["cases"]) == 1
        assert result["cases"][0]["case_id"] == "12345"
        assert result["cases"][0]["case_title"] == "Smith v. Jones"
        assert result["cases"][0]["court"] == "flsd"
        assert result["cases"][0]["filing_date"] == "2023-01-15"

    @pytest.mark.asyncio
    async def test_search_federal_cases_with_filters(self) -> None:
        server = CourtRecordsMCPServer(courtlistener_api_key="fake-key")
        server._provider = MagicMock()
        server._provider.search = AsyncMock(return_value=[])

        result = await server.search_federal_cases(
            "Smith", state="FL", case_type="civil"
        )

        server._provider.search.assert_called_once_with(
            party_name="Smith", state="FL", case_type="civil"
        )
        assert result["cases"] == []

    @pytest.mark.asyncio
    async def test_get_case_details(self) -> None:
        server = CourtRecordsMCPServer(courtlistener_api_key="fake-key")
        server._provider = MagicMock()
        server._provider.get_detail = AsyncMock(return_value={
            "id": 12345,
            "case_name": "Smith v. Jones",
            "court": "flsd",
            "date_filed": "2023-01-15",
            "status": "Open",
            "parties": [
                {"name": "John Smith", "role": "Plaintiff"},
                {"name": "Jane Jones", "role": "Defendant"},
            ],
            "absolute_url": "/docket/12345/smith-v-jones/",
        })

        result = await server.get_case_details("12345")

        assert result["case_id"] == "12345"
        assert result["case_title"] == "Smith v. Jones"
        assert len(result["parties"]) == 2
        assert result["parties"][0]["name"] == "John Smith"
        assert result["docket_url"] == "/docket/12345/smith-v-jones/"

    @pytest.mark.asyncio
    async def test_get_case_details_not_found(self) -> None:
        server = CourtRecordsMCPServer(courtlistener_api_key="fake-key")
        server._provider = MagicMock()
        server._provider.get_detail = AsyncMock(return_value=None)

        result = await server.get_case_details("99999")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_search_state_liens_courtlistener(self) -> None:
        server = CourtRecordsMCPServer(courtlistener_api_key="fake-key")
        server._provider = MagicMock()
        server._provider.search = AsyncMock(return_value=[
            {
                "filing_number": "LN-001",
                "debtor_name": "ACME LLC",
                "creditor_name": "IRS",
                "lien_amount": 50000,
                "dateFiled": "2023-06-01",
                "state": "FL",
            },
        ])

        result = await server.search_state_liens("ACME LLC", "FL")

        assert len(result["liens"]) == 1
        assert result["liens"][0]["debtor"] == "ACME LLC"
        assert result["liens"][0]["creditor"] == "IRS"

    @pytest.mark.asyncio
    async def test_search_state_liens_scraper_fallback(self) -> None:
        """Scraper runs even when CourtListener has results."""
        server = CourtRecordsMCPServer(courtlistener_api_key="fake-key")
        server._provider = MagicMock()
        server._provider.search = AsyncMock(return_value=[])
        server._lien_scraper.search = AsyncMock(return_value=[
            {"debtor": "ACME LLC", "creditor": "County Tax", "state": "FL"},
        ])

        result = await server.search_state_liens("ACME LLC", "FL")

        assert len(result["liens"]) == 1
        assert result["liens"][0]["creditor"] == "County Tax"

    @pytest.mark.asyncio
    async def test_search_state_liens_no_api_key(self) -> None:
        """Without API key, only scraper is used."""
        server = CourtRecordsMCPServer()
        server._lien_scraper.search = AsyncMock(return_value=[])

        result = await server.search_state_liens("ACME LLC", "FL")

        assert result["liens"] == []

    @pytest.mark.asyncio
    async def test_handle_call_dispatches(self) -> None:
        server = CourtRecordsMCPServer()
        result = await server.handle_call(
            "search_federal_cases", {"party_name": "Test"}
        )
        # Without API key, should return error
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Error Paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorPaths:
    @pytest.mark.asyncio
    async def test_search_no_api_key(self) -> None:
        server = CourtRecordsMCPServer()

        result = await server.search_federal_cases("Smith")

        assert "error" in result
        assert "not configured" in result["error"]
        assert result["cases"] == []

    @pytest.mark.asyncio
    async def test_search_http_error(self) -> None:
        server = CourtRecordsMCPServer(courtlistener_api_key="fake-key")
        resp = MagicMock()
        resp.status_code = 403
        server._provider = MagicMock()
        server._provider.search = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "forbidden", request=MagicMock(), response=resp
            )
        )

        result = await server.search_federal_cases("Smith")

        assert "error" in result
        assert "403" in result["error"]
        assert result["cases"] == []

    @pytest.mark.asyncio
    async def test_search_generic_exception(self) -> None:
        server = CourtRecordsMCPServer(courtlistener_api_key="fake-key")
        server._provider = MagicMock()
        server._provider.search = AsyncMock(
            side_effect=RuntimeError("network down")
        )

        result = await server.search_federal_cases("Smith")

        assert "error" in result
        assert "network down" in result["error"]

    @pytest.mark.asyncio
    async def test_details_no_api_key(self) -> None:
        server = CourtRecordsMCPServer()

        result = await server.get_case_details("12345")

        assert "error" in result
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_details_http_error(self) -> None:
        server = CourtRecordsMCPServer(courtlistener_api_key="fake-key")
        resp = MagicMock()
        resp.status_code = 404
        server._provider = MagicMock()
        server._provider.get_detail = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "not found", request=MagicMock(), response=resp
            )
        )

        result = await server.get_case_details("99999")

        assert "error" in result
        assert "404" in result["error"]

    @pytest.mark.asyncio
    async def test_details_generic_exception(self) -> None:
        server = CourtRecordsMCPServer(courtlistener_api_key="fake-key")
        server._provider = MagicMock()
        server._provider.get_detail = AsyncMock(
            side_effect=RuntimeError("timeout")
        )

        result = await server.get_case_details("12345")

        assert "error" in result
        assert "timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_liens_courtlistener_error_still_runs_scraper(self) -> None:
        """CourtListener error doesn't prevent scraper from running."""
        server = CourtRecordsMCPServer(courtlistener_api_key="fake-key")
        resp = MagicMock()
        resp.status_code = 500
        server._provider = MagicMock()
        server._provider.search = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "server error", request=MagicMock(), response=resp
            )
        )
        server._lien_scraper.search = AsyncMock(return_value=[])

        result = await server.search_state_liens("ACME", "FL")

        # Should still return successfully (empty) even with CL error
        assert "liens" in result
        server._lien_scraper.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_tool_raises_key_error(self) -> None:
        server = CourtRecordsMCPServer()
        with pytest.raises(KeyError, match="not_a_tool"):
            await server.handle_call("not_a_tool", {})


# ═══════════════════════════════════════════════════════════════════════════════
# Normalisation helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestNormalisation:
    def test_case_standard_courtlistener_fields(self) -> None:
        raw = {
            "docket_id": 123,
            "caseName": "Smith v. Jones",
            "court": "flsd",
            "dateFiled": "2023-01-15",
            "status": "Open",
            "absolute_url": "/docket/123/",
        }
        result = _normalise_case(raw)
        assert result["case_id"] == "123"
        assert result["case_title"] == "Smith v. Jones"
        assert result["court"] == "flsd"
        assert result["filing_date"] == "2023-01-15"
        assert result["docket_url"] == "/docket/123/"

    def test_case_alternate_field_names(self) -> None:
        raw = {
            "case_id": "456",
            "case_name": "Doe v. Roe",
            "court_name": "SDNY",
            "case_type": "civil",
            "filed_date": "2022-05-10",
            "case_status": "Closed",
        }
        result = _normalise_case(raw)
        assert result["case_id"] == "456"
        assert result["case_title"] == "Doe v. Roe"
        assert result["court"] == "SDNY"
        assert result["case_type"] == "civil"
        assert result["filing_date"] == "2022-05-10"
        assert result["status"] == "Closed"

    def test_case_prefers_docket_id(self) -> None:
        """docket_id (CourtListener primary key) takes precedence over id and case_id."""
        raw = {"docket_id": 100, "id": "C-3", "case_id": "C-2"}
        result = _normalise_case(raw)
        assert result["case_id"] == "100"

    def test_case_id_fallback_order(self) -> None:
        """Without docket_id, id takes precedence over case_id."""
        raw = {"id": "C-3", "case_id": "C-2"}
        result = _normalise_case(raw)
        assert result["case_id"] == "C-3"

    def test_case_with_parties(self) -> None:
        raw = {
            "id": 789,
            "title": "Test Case",
            "parties": [
                {"name": "Alice", "role": "Plaintiff"},
                {"party_name": "Bob", "party_type": "Defendant"},
            ],
        }
        result = _normalise_case(raw)
        assert len(result["parties"]) == 2
        assert result["parties"][0]["name"] == "Alice"
        assert result["parties"][0]["role"] == "Plaintiff"
        assert result["parties"][1]["name"] == "Bob"
        assert result["parties"][1]["role"] == "Defendant"

    def test_case_empty_parties(self) -> None:
        result = _normalise_case({"id": 1})
        assert result["parties"] == []

    def test_case_non_list_parties(self) -> None:
        """If parties is not a list (bad data), return empty list."""
        result = _normalise_case({"id": 1, "parties": "bad data"})
        assert result["parties"] == []

    def test_case_handles_missing(self) -> None:
        result = _normalise_case({})
        assert result["case_id"] == "None"  # str(None) since all three are None
        assert result["parties"] == []

    def test_lien_standard_fields(self) -> None:
        raw = {
            "filing_number": "LN-001",
            "debtor": "ACME LLC",
            "creditor": "IRS",
            "amount": 50000,
            "filing_date": "2023-06-01",
            "lien_type": "tax",
            "state": "FL",
        }
        result = _normalise_lien(raw)
        assert result["filing_number"] == "LN-001"
        assert result["debtor"] == "ACME LLC"
        assert result["creditor"] == "IRS"
        assert result["amount"] == 50000
        assert result["lien_type"] == "tax"

    def test_lien_alternate_field_names(self) -> None:
        raw = {
            "instrument_number": "LN-002",
            "debtor_name": "XYZ Corp",
            "creditor_name": "State of FL",
            "lien_amount": 25000,
            "recorded_date": "2023-07-15",
            "type": "judgment",
            "state": "FL",
        }
        result = _normalise_lien(raw)
        assert result["filing_number"] == "LN-002"
        assert result["debtor"] == "XYZ Corp"
        assert result["creditor"] == "State of FL"
        assert result["amount"] == 25000
        assert result["filing_date"] == "2023-07-15"
        assert result["lien_type"] == "judgment"

    def test_lien_prefers_primary_keys(self) -> None:
        raw = {"filing_number": "F-1", "instrument_number": "F-2"}
        result = _normalise_lien(raw)
        assert result["filing_number"] == "F-1"

    def test_lien_courtlistener_date_fields(self) -> None:
        """CourtListener uses dateFiled / date_filed."""
        raw = {"dateFiled": "2023-01-01"}
        result = _normalise_lien(raw)
        assert result["filing_date"] == "2023-01-01"

        raw2 = {"date_filed": "2023-02-02"}
        result2 = _normalise_lien(raw2)
        assert result2["filing_date"] == "2023-02-02"

    def test_lien_empty(self) -> None:
        result = _normalise_lien({})
        assert result["filing_number"] is None
        assert result["debtor"] is None
        assert result["state"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════════════════════


class TestFactory:
    def test_with_api_key(self) -> None:
        with patch("aloha.config.settings") as mock_settings:
            mock_settings.courtlistener_api_key = "test-key-123"
            server = create_court_records_server()
            assert isinstance(server, CourtRecordsMCPServer)
            assert server._provider is not None

    def test_without_api_key(self) -> None:
        """Should still create server (graceful degradation)."""
        with patch("aloha.config.settings") as mock_settings:
            mock_settings.courtlistener_api_key = None
            server = create_court_records_server()
            assert isinstance(server, CourtRecordsMCPServer)
            assert server._provider is None
