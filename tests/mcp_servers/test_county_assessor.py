"""Tests for the County Assessor MCP Server."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aloha.mcp_servers.county_assessor.server import (
    CountyAssessorMCPServer,
    create_county_assessor_server,
)


# -- Init & Tool Registration -------------------------------------------------

class TestInit:
    def test_server_name(self) -> None:
        server = CountyAssessorMCPServer()
        assert server.name == "county_assessor"

    def test_tools_registered(self) -> None:
        server = CountyAssessorMCPServer()
        assert "lookup_parcel" in server.tools
        assert "search_by_address" in server.tools
        assert "search_by_owner" in server.tools

    def test_tool_count(self) -> None:
        server = CountyAssessorMCPServer()
        assert len(server.tools) == 3

    def test_lookup_parcel_schema(self) -> None:
        server = CountyAssessorMCPServer()
        schema = server.tools["lookup_parcel"].input_schema
        assert set(schema["required"]) == {"parcel_id", "state", "county"}


# -- Success Paths (mocked scrapers) ------------------------------------------

class TestSuccessPaths:
    @pytest.mark.asyncio
    async def test_lookup_parcel_arcgis_success(self) -> None:
        server = CountyAssessorMCPServer()
        mock_result = {"parcel_id": "123", "address": "456 Main St"}
        mock_scraper = MagicMock()
        mock_scraper.query_by_apn = AsyncMock(return_value=mock_result)
        mock_scraper.close = AsyncMock()

        with (
            patch(
                "aloha.agents.parcel_research.tools._ARCGIS_ENDPOINTS",
                {("FL", "orange"): "https://example.com/arcgis"},
            ),
            patch(
                "aloha.scrapers.tier1_apis.arcgis.ArcGISParcelScraper",
                return_value=mock_scraper,
            ),
        ):
            result = await server.lookup_parcel("123", "FL", "orange")
        assert result["parcel_id"] == "123"

    @pytest.mark.asyncio
    async def test_lookup_parcel_falls_back_to_qpublic(self) -> None:
        server = CountyAssessorMCPServer()
        mock_qpublic_result = {"parcel_id": "456", "address": "789 Oak Ave"}
        mock_qpublic_scraper = MagicMock()
        mock_qpublic_scraper.query_by_apn = AsyncMock(return_value=mock_qpublic_result)

        with (
            patch(
                "aloha.agents.parcel_research.tools._ARCGIS_ENDPOINTS",
                {},
            ),
            patch(
                "aloha.scrapers.tier2_vendors.qpublic.get_qpublic_scraper",
                return_value=mock_qpublic_scraper,
            ),
        ):
            result = await server.lookup_parcel("456", "GA", "dekalb")
        assert result["parcel_id"] == "456"

    @pytest.mark.asyncio
    async def test_lookup_parcel_falls_back_to_tyler(self) -> None:
        server = CountyAssessorMCPServer()
        mock_tyler_result = {"owner_of_record": "Jane Doe"}
        mock_tyler_scraper = MagicMock()
        mock_tyler_scraper.query_by_apn = AsyncMock(return_value=mock_tyler_result)

        with (
            patch(
                "aloha.agents.parcel_research.tools._ARCGIS_ENDPOINTS",
                {},
            ),
            patch(
                "aloha.scrapers.tier2_vendors.qpublic.get_qpublic_scraper",
                return_value=None,
            ),
            patch(
                "aloha.scrapers.tier2_vendors.tyler.get_eagleweb_scraper",
                return_value=mock_tyler_scraper,
            ),
        ):
            result = await server.lookup_parcel("789", "SC", "greenville")
        assert result["owner_of_record"] == "Jane Doe"

    @pytest.mark.asyncio
    async def test_search_by_address_arcgis(self) -> None:
        server = CountyAssessorMCPServer()
        mock_scraper = MagicMock()
        mock_scraper.query_by_address = AsyncMock(return_value=[{"parcel_id": "A1"}])
        mock_scraper.close = AsyncMock()

        with (
            patch(
                "aloha.agents.parcel_research.tools._ARCGIS_ENDPOINTS",
                {("FL", "orange"): "https://example.com/arcgis"},
            ),
            patch(
                "aloha.scrapers.tier1_apis.arcgis.ArcGISParcelScraper",
                return_value=mock_scraper,
            ),
        ):
            result = await server.search_by_address("123 Main", "FL", "orange")
        assert len(result["parcels"]) == 1

    @pytest.mark.asyncio
    async def test_search_by_owner_returns_stub(self) -> None:
        server = CountyAssessorMCPServer()
        result = await server.search_by_owner("Doe", "FL", "orange")
        assert result["stub"] is True
        assert result["parcels"] == []


# -- Error Paths ---------------------------------------------------------------

class TestErrorPaths:
    @pytest.mark.asyncio
    async def test_lookup_no_scraper_available(self) -> None:
        server = CountyAssessorMCPServer()
        with (
            patch(
                "aloha.agents.parcel_research.tools._ARCGIS_ENDPOINTS",
                {},
            ),
            patch(
                "aloha.scrapers.tier2_vendors.qpublic.get_qpublic_scraper",
                return_value=None,
            ),
            patch(
                "aloha.scrapers.tier2_vendors.tyler.get_eagleweb_scraper",
                return_value=None,
            ),
        ):
            result = await server.lookup_parcel("999", "ZZ", "nowhere")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_by_address_no_endpoint(self) -> None:
        server = CountyAssessorMCPServer()
        with patch(
            "aloha.agents.parcel_research.tools._ARCGIS_ENDPOINTS",
            {},
        ):
            result = await server.search_by_address("123 Main", "ZZ", "nowhere")
        assert "error" in result
        assert result["parcels"] == []

    @pytest.mark.asyncio
    async def test_arcgis_exception_falls_through(self) -> None:
        server = CountyAssessorMCPServer()
        mock_scraper = MagicMock()
        mock_scraper.query_by_apn = AsyncMock(side_effect=Exception("network"))
        mock_scraper.close = AsyncMock()

        with (
            patch(
                "aloha.agents.parcel_research.tools._ARCGIS_ENDPOINTS",
                {("FL", "orange"): "https://example.com/arcgis"},
            ),
            patch(
                "aloha.scrapers.tier1_apis.arcgis.ArcGISParcelScraper",
                return_value=mock_scraper,
            ),
            patch(
                "aloha.scrapers.tier2_vendors.qpublic.get_qpublic_scraper",
                return_value=None,
            ),
            patch(
                "aloha.scrapers.tier2_vendors.tyler.get_eagleweb_scraper",
                return_value=None,
            ),
        ):
            result = await server.lookup_parcel("123", "FL", "orange")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_unknown_tool_raises_key_error(self) -> None:
        server = CountyAssessorMCPServer()
        with pytest.raises(KeyError):
            await server.handle_call("nonexistent", {})


# -- Factory -------------------------------------------------------------------

class TestFactory:
    def test_create_county_assessor_server(self) -> None:
        server = create_county_assessor_server()
        assert isinstance(server, CountyAssessorMCPServer)
        assert server.name == "county_assessor"
