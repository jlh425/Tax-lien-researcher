"""Tests for the People Data MCP Server."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aloha.mcp_servers.people_data.server import (
    PeopleDataMCPServer,
    _normalise_hunter_verification,
    _normalise_pdl_person,
    create_people_data_server,
)


# -- Init & Tool Registration -------------------------------------------------

class TestInit:
    def test_server_name(self) -> None:
        server = PeopleDataMCPServer(pdl_api_key="pdl", hunter_api_key="hunter")
        assert server.name == "people_data"

    def test_tools_registered(self) -> None:
        server = PeopleDataMCPServer(pdl_api_key="pdl", hunter_api_key="hunter")
        assert "enrich_person" in server.tools
        assert "verify_email" in server.tools
        assert "search_phone" in server.tools

    def test_tool_count(self) -> None:
        server = PeopleDataMCPServer(pdl_api_key="pdl", hunter_api_key="hunter")
        assert len(server.tools) == 3

    def test_client_initially_none(self) -> None:
        server = PeopleDataMCPServer(pdl_api_key="pdl", hunter_api_key="hunter")
        assert server._client is None


# -- Success Paths (mocked HTTP) -----------------------------------------------

class TestSuccessPaths:
    @pytest.mark.asyncio
    async def test_enrich_person_success(self) -> None:
        server = PeopleDataMCPServer(pdl_api_key="pdl", hunter_api_key="hunter")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "full_name": "John Doe",
            "first_name": "John",
            "last_name": "Doe",
            "emails": ["john@example.com"],
            "phone_numbers": ["+14155551234"],
            "linkedin_url": "https://linkedin.com/in/johndoe",
            "location_name": "Orlando, FL",
            "job_company_name": "Acme Corp",
            "job_title": "CEO",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        server._client = mock_client

        result = await server.enrich_person("John Doe", location="Orlando, FL")
        assert result["full_name"] == "John Doe"
        assert result["company"] == "Acme Corp"
        assert len(result["emails"]) == 1

    @pytest.mark.asyncio
    async def test_verify_email_success(self) -> None:
        server = PeopleDataMCPServer(pdl_api_key="pdl", hunter_api_key="hunter")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "email": "john@example.com",
                "status": "valid",
                "score": 95,
                "disposable": False,
                "webmail": False,
                "mx_records": True,
            },
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        server._client = mock_client

        result = await server.verify_email("john@example.com")
        assert result["email"] == "john@example.com"
        assert result["status"] == "valid"
        assert result["score"] == 95

    @pytest.mark.asyncio
    async def test_search_phone_success(self) -> None:
        server = PeopleDataMCPServer(pdl_api_key="pdl", hunter_api_key="hunter")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"full_name": "Jane Doe", "first_name": "Jane", "last_name": "Doe"},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        server._client = mock_client

        result = await server.search_phone("+14155551234")
        assert len(result["persons"]) == 1
        assert result["persons"][0]["full_name"] == "Jane Doe"

    @pytest.mark.asyncio
    async def test_close_cleans_up(self) -> None:
        server = PeopleDataMCPServer(pdl_api_key="pdl", hunter_api_key="hunter")
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        server._client = mock_client

        await server.close()
        mock_client.aclose.assert_awaited_once()
        assert server._client is None


# -- Error Paths ---------------------------------------------------------------

class TestErrorPaths:
    @pytest.mark.asyncio
    async def test_enrich_person_http_error(self) -> None:
        server = PeopleDataMCPServer(pdl_api_key="pdl", hunter_api_key="hunter")
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 402
        error = httpx.HTTPStatusError("Payment Required", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=error)
        mock_client.is_closed = False
        server._client = mock_client

        result = await server.enrich_person("Test")
        assert "error" in result
        assert "402" in result["error"]

    @pytest.mark.asyncio
    async def test_verify_email_exception(self) -> None:
        server = PeopleDataMCPServer(pdl_api_key="pdl", hunter_api_key="hunter")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
        mock_client.is_closed = False
        server._client = mock_client

        result = await server.verify_email("bad@example.com")
        assert "error" in result
        assert "connection refused" in result["error"]

    @pytest.mark.asyncio
    async def test_search_phone_http_error(self) -> None:
        server = PeopleDataMCPServer(pdl_api_key="pdl", hunter_api_key="hunter")
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        error = httpx.HTTPStatusError("Rate limit", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=error)
        mock_client.is_closed = False
        server._client = mock_client

        result = await server.search_phone("+1234")
        assert "error" in result
        assert result["persons"] == []

    @pytest.mark.asyncio
    async def test_unknown_tool_raises_key_error(self) -> None:
        server = PeopleDataMCPServer(pdl_api_key="pdl", hunter_api_key="hunter")
        with pytest.raises(KeyError):
            await server.handle_call("nope", {})


# -- Normalisation Helpers -----------------------------------------------------

class TestNormalisation:
    def test_normalise_pdl_person(self) -> None:
        raw = {
            "full_name": "Alice Bob",
            "first_name": "Alice",
            "last_name": "Bob",
            "emails": ["alice@example.com"],
            "phone_numbers": ["+1111"],
            "linkedin_url": "https://linkedin.com/in/alice",
            "location_name": "NYC",
            "job_company_name": "TechCo",
            "job_title": "Engineer",
        }
        result = _normalise_pdl_person(raw)
        assert result["full_name"] == "Alice Bob"
        assert result["company"] == "TechCo"
        assert result["title"] == "Engineer"

    def test_normalise_pdl_person_empty(self) -> None:
        result = _normalise_pdl_person({})
        assert result["full_name"] is None
        assert result["emails"] == []
        assert result["phone_numbers"] == []

    def test_normalise_hunter_verification(self) -> None:
        raw = {
            "data": {
                "email": "test@example.com",
                "status": "valid",
                "score": 90,
                "disposable": False,
                "webmail": True,
                "mx_records": True,
            },
        }
        result = _normalise_hunter_verification(raw)
        assert result["email"] == "test@example.com"
        assert result["status"] == "valid"
        assert result["webmail"] is True

    def test_normalise_hunter_flat_response(self) -> None:
        raw = {"email": "a@b.com", "result": "undeliverable", "score": 10}
        result = _normalise_hunter_verification(raw)
        assert result["email"] == "a@b.com"
        assert result["status"] == "undeliverable"


# -- Factory -------------------------------------------------------------------

class TestFactory:
    def test_create_people_data_server_missing_both_keys(self) -> None:
        with patch("aloha.config.settings") as mock_settings:
            mock_settings.people_data_labs_api_key = None
            mock_settings.hunter_io_api_key = None
            with pytest.raises(ValueError, match="PEOPLE_DATA_LABS_API_KEY"):
                create_people_data_server()

    def test_create_people_data_server_missing_hunter(self) -> None:
        with patch("aloha.config.settings") as mock_settings:
            mock_settings.people_data_labs_api_key = "pdl-key"
            mock_settings.hunter_io_api_key = None
            with pytest.raises(ValueError, match="HUNTER_IO_API_KEY"):
                create_people_data_server()

    def test_create_people_data_server_success(self) -> None:
        with patch("aloha.config.settings") as mock_settings:
            mock_settings.people_data_labs_api_key = "pdl-key"
            mock_settings.hunter_io_api_key = "hunter-key"
            server = create_people_data_server()
            assert isinstance(server, PeopleDataMCPServer)
            assert server._pdl_api_key == "pdl-key"
