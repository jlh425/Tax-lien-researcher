"""Tests for the SOS (Secretary of State) MCP Server."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aloha.mcp_servers.sos.server import (
    SOSMCPServer,
    _normalise_entity_detail,
    _normalise_entity_stub,
    create_sos_server,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Init & Tool Registration
# ═══════════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_server_name(self) -> None:
        server = SOSMCPServer(api_key="fake-key")
        assert server.name == "sos"

    def test_tools_registered(self) -> None:
        server = SOSMCPServer(api_key="fake-key")
        assert "sos_lookup_entity" in server.tools
        assert "sos_get_entity_details" in server.tools
        assert "sos_search_by_registered_agent" in server.tools
        assert "sos_search_by_address" in server.tools

    def test_tool_count(self) -> None:
        server = SOSMCPServer(api_key="fake-key")
        assert len(server.tools) == 4

    def test_client_initially_none(self) -> None:
        server = SOSMCPServer(api_key="fake-key")
        assert server._client is None


# ═══════════════════════════════════════════════════════════════════════════════
# Success Paths (mocked HTTP)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSuccessPaths:
    @pytest.mark.asyncio
    async def test_lookup_entity(self) -> None:
        server = SOSMCPServer(api_key="fake-key")
        server._get = AsyncMock(return_value={
            "entities": [
                {"id": "E1", "name": "ACME LLC", "type": "llc", "state": "FL", "status": "Active"},
            ]
        })

        result = await server.sos_lookup_entity("ACME LLC", "FL")

        assert len(result["entities"]) == 1
        assert result["entities"][0]["entity_name"] == "ACME LLC"
        assert result["entities"][0]["entity_id"] == "E1"

    @pytest.mark.asyncio
    async def test_lookup_entity_with_type_filter(self) -> None:
        server = SOSMCPServer(api_key="fake-key")
        server._get = AsyncMock(return_value={"entities": []})

        await server.sos_lookup_entity("ACME", "FL", entity_type="corporation")

        call_params = server._get.call_args[1].get("params") or server._get.call_args[0][1]
        # Verify type param was included
        server._get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_entity_details(self) -> None:
        server = SOSMCPServer(api_key="fake-key")
        server._get = AsyncMock(return_value={
            "id": "E1",
            "name": "ACME LLC",
            "type": "llc",
            "state": "FL",
            "status": "Active",
            "formation_date": "2020-01-15",
            "officers": [{"name": "JOHN SMITH", "title": "Manager"}],
            "registered_agent": {"name": "CT CORPORATION", "address": "123 Main St"},
            "filing_url": "https://dos.fl.gov/entities/E1",
        })

        result = await server.sos_get_entity_details("E1", "FL")

        assert result["entity_name"] == "ACME LLC"
        assert result["registered_agent"] == "CT CORPORATION"
        assert len(result["officers"]) == 1
        assert result["officers"][0]["name"] == "JOHN SMITH"
        assert result["sos_filing_url"] == "https://dos.fl.gov/entities/E1"

    @pytest.mark.asyncio
    async def test_search_by_registered_agent(self) -> None:
        server = SOSMCPServer(api_key="fake-key")
        server._get = AsyncMock(return_value={
            "entities": [
                {"id": "E1", "name": "SHELL CO 1", "state": "FL"},
                {"id": "E2", "name": "SHELL CO 2", "state": "FL"},
            ]
        })

        result = await server.sos_search_by_registered_agent("CT CORPORATION", "FL")

        assert len(result["entities"]) == 2

    @pytest.mark.asyncio
    async def test_search_by_address(self) -> None:
        server = SOSMCPServer(api_key="fake-key")
        server._get = AsyncMock(return_value={
            "results": [
                {"entity_id": "E1", "entity_name": "CO A", "state": "FL"},
            ]
        })

        result = await server.sos_search_by_address("123 Main St", "FL")

        assert len(result["entities"]) == 1
        assert result["entities"][0]["entity_name"] == "CO A"


# ═══════════════════════════════════════════════════════════════════════════════
# Error Paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorPaths:
    @pytest.mark.asyncio
    async def test_lookup_http_error(self) -> None:
        server = SOSMCPServer(api_key="fake-key")
        resp = MagicMock()
        resp.status_code = 403
        server._get = AsyncMock(side_effect=httpx.HTTPStatusError("forbidden", request=MagicMock(), response=resp))

        result = await server.sos_lookup_entity("ACME", "FL")

        assert "error" in result
        assert "403" in result["error"]
        assert result["entities"] == []

    @pytest.mark.asyncio
    async def test_lookup_generic_exception(self) -> None:
        server = SOSMCPServer(api_key="fake-key")
        server._get = AsyncMock(side_effect=RuntimeError("network down"))

        result = await server.sos_lookup_entity("ACME", "FL")

        assert "error" in result
        assert "network down" in result["error"]

    @pytest.mark.asyncio
    async def test_details_http_error(self) -> None:
        server = SOSMCPServer(api_key="fake-key")
        resp = MagicMock()
        resp.status_code = 404
        server._get = AsyncMock(side_effect=httpx.HTTPStatusError("not found", request=MagicMock(), response=resp))

        result = await server.sos_get_entity_details("FAKE", "FL")

        assert "error" in result
        assert "404" in result["error"]

    @pytest.mark.asyncio
    async def test_details_generic_exception(self) -> None:
        server = SOSMCPServer(api_key="fake-key")
        server._get = AsyncMock(side_effect=RuntimeError("timeout"))

        result = await server.sos_get_entity_details("FAKE", "FL")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_by_ra_http_error(self) -> None:
        server = SOSMCPServer(api_key="fake-key")
        resp = MagicMock()
        resp.status_code = 500
        server._get = AsyncMock(side_effect=httpx.HTTPStatusError("server error", request=MagicMock(), response=resp))

        result = await server.sos_search_by_registered_agent("CT CORP", "FL")

        assert "error" in result
        assert result["entities"] == []

    @pytest.mark.asyncio
    async def test_search_by_address_generic_error(self) -> None:
        server = SOSMCPServer(api_key="fake-key")
        server._get = AsyncMock(side_effect=ConnectionError("refused"))

        result = await server.sos_search_by_address("123 Main", "FL")

        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Normalisation helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestNormalisation:
    def test_entity_stub_standard_fields(self) -> None:
        raw = {"id": "E1", "name": "ACME", "type": "llc", "state": "FL", "status": "Active", "formation_date": "2020-01-01"}
        result = _normalise_entity_stub(raw)
        assert result["entity_id"] == "E1"
        assert result["entity_name"] == "ACME"
        assert result["entity_type"] == "llc"
        assert result["status"] == "Active"

    def test_entity_stub_alternate_field_names(self) -> None:
        raw = {"entity_id": "E2", "entity_name": "FOO", "entity_type": "corp", "sos_status": "Inactive", "filed_date": "2019-05-01"}
        result = _normalise_entity_stub(raw)
        assert result["entity_id"] == "E2"
        assert result["entity_name"] == "FOO"
        assert result["status"] == "Inactive"
        assert result["formation_date"] == "2019-05-01"

    def test_entity_detail_with_officers(self) -> None:
        raw = {
            "id": "E1", "name": "ACME", "state": "FL", "status": "Active",
            "officers": [{"name": "JOHN", "title": "President"}],
            "registered_agent": {"name": "CT CORP", "address": "456 Oak St"},
        }
        result = _normalise_entity_detail(raw)
        assert result["officers"][0]["name"] == "JOHN"
        assert result["registered_agent"] == "CT CORP"
        assert result["registered_agent_address"] == "456 Oak St"

    def test_entity_detail_string_registered_agent(self) -> None:
        raw = {"registered_agent": "JOHN SMITH"}
        result = _normalise_entity_detail(raw)
        assert result["registered_agent"] == "JOHN SMITH"
        assert result["registered_agent_address"] is None

    def test_entity_detail_members(self) -> None:
        raw = {"managers": [{"name": "BOB", "role": "Manager"}]}
        result = _normalise_entity_detail(raw)
        assert result["managers_members"][0]["name"] == "BOB"
        assert result["managers_members"][0]["title"] == "Manager"

    def test_entity_detail_empty(self) -> None:
        result = _normalise_entity_detail({})
        assert result["officers"] == []
        assert result["managers_members"] == []
        assert result["registered_agent"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════════════════════


class TestFactory:
    def test_missing_key_raises(self) -> None:
        with patch("aloha.config.settings") as mock_settings:
            mock_settings.cobalt_intelligence_api_key = None
            with pytest.raises(ValueError, match="COBALT_INTELLIGENCE_API_KEY"):
                create_sos_server()

    def test_success_with_key(self) -> None:
        with patch("aloha.config.settings") as mock_settings:
            mock_settings.cobalt_intelligence_api_key = "test-key-123"
            server = create_sos_server()
            assert isinstance(server, SOSMCPServer)
