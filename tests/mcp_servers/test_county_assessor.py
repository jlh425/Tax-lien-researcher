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
    async def test_search_by_owner_arcgis_success(self) -> None:
        server = CountyAssessorMCPServer()
        mock_scraper = MagicMock()
        mock_scraper._query = AsyncMock(return_value={
            "features": [
                {
                    "attributes": {"APN": "111", "OWNER": "DOE JOHN", "SITUS_ADDR": "123 Main"},
                    "geometry": {"x": -81.38, "y": 28.54},
                },
                {
                    "attributes": {"APN": "222", "OWNER": "DOE JANE", "SITUS_ADDR": "456 Oak"},
                    "geometry": {"x": -81.39, "y": 28.55},
                },
            ]
        })
        mock_scraper._normalise = MagicMock(side_effect=lambda f: {
            "parcel_id": f["attributes"]["APN"],
            "owner_of_record": f["attributes"]["OWNER"],
        })
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
            result = await server.search_by_owner("Doe", "FL", "orange")
        assert len(result["parcels"]) == 2
        assert result["parcels"][0]["owner_of_record"] == "DOE JOHN"

    @pytest.mark.asyncio
    async def test_search_by_owner_no_scraper(self) -> None:
        server = CountyAssessorMCPServer()
        with (
            patch("aloha.agents.parcel_research.tools._ARCGIS_ENDPOINTS", {}),
            patch("aloha.scrapers.tier2_vendors.qpublic.get_qpublic_scraper", return_value=None),
            patch("aloha.scrapers.tier2_vendors.tyler.get_eagleweb_scraper", return_value=None),
        ):
            result = await server.search_by_owner("Doe", "ZZ", "nowhere")
        assert "error" in result
        assert result["parcels"] == []

    @pytest.mark.asyncio
    async def test_search_by_owner_arcgis_no_results_tries_aliases(self) -> None:
        """When first owner field returns nothing, tries next alias."""
        server = CountyAssessorMCPServer()
        call_count = 0

        async def mock_query(**kwargs):
            nonlocal call_count
            call_count += 1
            # Return empty for first alias, results for second
            if call_count == 1:
                return {"features": []}
            return {"features": [
                {"attributes": {"APN": "333", "OWN_NAME": "DOE"}, "geometry": {"x": -81, "y": 28}},
            ]}

        mock_scraper = MagicMock()
        mock_scraper._query = AsyncMock(side_effect=mock_query)
        mock_scraper._normalise = MagicMock(return_value={"parcel_id": "333", "owner_of_record": "DOE"})
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
            result = await server.search_by_owner("Doe", "FL", "orange")
        assert len(result["parcels"]) == 1
        assert call_count >= 2


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
