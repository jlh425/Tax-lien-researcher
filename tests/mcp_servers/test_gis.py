"""Tests for the GIS MCP Server."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aloha.mcp_servers.gis.server import (
    GISMCPServer,
    _normalise_geocode_result,
    create_gis_server,
)


# -- Init & Tool Registration -------------------------------------------------

class TestInit:
    def test_server_name(self) -> None:
        server = GISMCPServer(api_key="test-key")
        assert server.name == "gis"

    def test_tools_registered(self) -> None:
        server = GISMCPServer(api_key="test-key")
        assert "geocode_address" in server.tools
        assert "reverse_geocode" in server.tools
        assert "get_parcel_boundary" in server.tools

    def test_tool_count(self) -> None:
        server = GISMCPServer(api_key="test-key")
        assert len(server.tools) == 3

    def test_client_initially_none(self) -> None:
        server = GISMCPServer(api_key="test-key")
        assert server._client is None


# -- Success Paths (mocked HTTP) -----------------------------------------------

class TestSuccessPaths:
    @pytest.mark.asyncio
    async def test_geocode_address_success(self) -> None:
        server = GISMCPServer(api_key="test-key")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "OK",
            "results": [{
                "formatted_address": "123 Main St, Orlando, FL 32801",
                "geometry": {"location": {"lat": 28.54, "lng": -81.38}, "location_type": "ROOFTOP"},
                "place_id": "ChIJ_test",
                "address_components": [
                    {"types": ["street_number"], "long_name": "123"},
                    {"types": ["route"], "long_name": "Main St"},
                ],
            }],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        server._client = mock_client

        result = await server.geocode_address("123 Main St, Orlando, FL")
        assert len(result["results"]) == 1
        assert result["results"][0]["latitude"] == 28.54
        assert result["results"][0]["longitude"] == -81.38
        assert result["results"][0]["place_id"] == "ChIJ_test"

    @pytest.mark.asyncio
    async def test_reverse_geocode_success(self) -> None:
        server = GISMCPServer(api_key="test-key")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "OK",
            "results": [{
                "formatted_address": "123 Main St, Orlando, FL 32801",
                "geometry": {"location": {"lat": 28.54, "lng": -81.38}},
                "place_id": "ChIJ_test",
                "address_components": [],
            }],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        server._client = mock_client

        result = await server.reverse_geocode(28.54, -81.38)
        assert len(result["results"]) == 1
        assert result["results"][0]["formatted_address"] == "123 Main St, Orlando, FL 32801"

    @pytest.mark.asyncio
    async def test_get_parcel_boundary_stub(self) -> None:
        server = GISMCPServer(api_key="test-key")
        result = await server.get_parcel_boundary("123", "FL", "orange")
        assert result["stub"] is True
        assert result["boundary"] is None

    @pytest.mark.asyncio
    async def test_close_cleans_up(self) -> None:
        server = GISMCPServer(api_key="test-key")
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
    async def test_geocode_non_ok_status(self) -> None:
        server = GISMCPServer(api_key="test-key")
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ZERO_RESULTS", "results": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        server._client = mock_client

        result = await server.geocode_address("nonexistent address")
        assert "error" in result
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_geocode_http_error(self) -> None:
        server = GISMCPServer(api_key="test-key")
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 403
        error = httpx.HTTPStatusError("Forbidden", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=error)
        mock_client.is_closed = False
        server._client = mock_client

        result = await server.geocode_address("123 Main")
        assert "error" in result
        assert "403" in result["error"]

    @pytest.mark.asyncio
    async def test_reverse_geocode_exception(self) -> None:
        server = GISMCPServer(api_key="test-key")
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("timeout"))
        mock_client.is_closed = False
        server._client = mock_client

        result = await server.reverse_geocode(0.0, 0.0)
        assert "error" in result
        assert "timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_tool_raises_key_error(self) -> None:
        server = GISMCPServer(api_key="test-key")
        with pytest.raises(KeyError):
            await server.handle_call("bad_tool", {})


# -- Normalisation Helpers -----------------------------------------------------

class TestNormalisation:
    def test_normalise_geocode_result(self) -> None:
        raw = {
            "formatted_address": "123 Main St",
            "geometry": {
                "location": {"lat": 28.54, "lng": -81.38},
                "location_type": "ROOFTOP",
            },
            "place_id": "ChIJ_test",
            "address_components": [
                {"types": ["locality"], "long_name": "Orlando"},
                {"types": ["administrative_area_level_1"], "long_name": "Florida"},
            ],
        }
        result = _normalise_geocode_result(raw)
        assert result["latitude"] == 28.54
        assert result["longitude"] == -81.38
        assert result["place_id"] == "ChIJ_test"
        assert result["location_type"] == "ROOFTOP"
        assert result["components"]["locality"] == "Orlando"

    def test_normalise_empty_result(self) -> None:
        result = _normalise_geocode_result({})
        assert result["latitude"] is None
        assert result["longitude"] is None
        assert result["components"] == {}


# -- Factory -------------------------------------------------------------------

class TestFactory:
    def test_create_gis_server_missing_key_raises(self) -> None:
        with patch("aloha.config.settings") as mock_settings:
            mock_settings.google_maps_api_key = None
            with pytest.raises(ValueError, match="GOOGLE_MAPS_API_KEY"):
                create_gis_server()

    def test_create_gis_server_with_key(self) -> None:
        with patch("aloha.config.settings") as mock_settings:
            mock_settings.google_maps_api_key = "test-key-123"
            server = create_gis_server()
            assert isinstance(server, GISMCPServer)
            assert server._api_key == "test-key-123"
