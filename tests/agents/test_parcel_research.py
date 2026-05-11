"""Unit tests for the Parcel Research Agent (no DB, no LLM, no network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aloha.agents.parcel_research.tools import (
    classify_property_type,
    parse_legal_description,
    query_assessor_web,
)


# ═══════════════════════════════════════════════════════════════════════════════
# parse_legal_description
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseLegalDescription:
    def test_lot_block_subdivision(self):
        result = parse_legal_description("LOT 5 BLK 3 SUNRISE ESTATES")
        assert result["format"] == "lot_block"
        assert result["lot"] == "5"
        assert result["block"] == "3"
        assert result["subdivision"] == "SUNRISE ESTATES"

    def test_lot_only(self):
        result = parse_legal_description("LOT 12 PALM GARDENS")
        assert result["format"] == "lot_block"
        assert result["lot"] == "12"
        assert result["block"] is None

    def test_metes_bounds(self):
        result = parse_legal_description("COM AT NW COR SEC 14 T2S R3E")
        assert result["format"] == "metes_bounds"
        assert result["section"] == "14"
        assert result["township"] == "2S"
        assert result["range"] == "3E"

    def test_metes_bounds_section_only(self):
        result = parse_legal_description("SEC 7 SOME DESCRIPTION")
        assert result["format"] == "metes_bounds"
        assert result["section"] == "7"

    def test_condo(self):
        result = parse_legal_description("UNIT 12B BLDG 3 HARBOR TOWERS CONDO")
        assert result["format"] == "condo"
        assert result["unit"] == "12B"
        assert result["building"] == "3"

    def test_unit_no_building(self):
        result = parse_legal_description("UNIT 5A SEASIDE VILLAS")
        assert result["format"] == "condo"
        assert result["unit"] == "5A"
        assert result["building"] is None

    def test_empty(self):
        result = parse_legal_description("")
        assert result["format"] == "unknown"
        assert result["raw"] == ""

    def test_none(self):
        result = parse_legal_description(None)
        assert result["format"] == "unknown"

    def test_unrecognized_format(self):
        result = parse_legal_description("SOME RANDOM TEXT")
        assert result["format"] == "unknown"

    def test_preserves_raw(self):
        desc = "LOT 1 BLK 2 DEMO"
        result = parse_legal_description(desc)
        assert result["raw"] == desc


# ═══════════════════════════════════════════════════════════════════════════════
# classify_property_type
# ═══════════════════════════════════════════════════════════════════════════════


class TestClassifyPropertyType:
    def test_residential_land_use_code(self):
        assert classify_property_type("01", None, None) == "residential"

    def test_commercial_land_use_code(self):
        assert classify_property_type("21", None, None) == "commercial"

    def test_industrial_land_use_code(self):
        assert classify_property_type("30", None, None) == "industrial"

    def test_agricultural_land_use_code(self):
        assert classify_property_type("40", None, None) == "agricultural"

    def test_vacant_land_code(self):
        assert classify_property_type("50", None, None) == "land"

    def test_residential_zoning_fallback(self):
        assert classify_property_type(None, "RS-1", None) == "residential"

    def test_commercial_zoning_fallback(self):
        assert classify_property_type(None, "C1", None) == "commercial"

    def test_industrial_zoning_fallback(self):
        assert classify_property_type(None, "M1", None) == "industrial"

    def test_agricultural_zoning_fallback(self):
        assert classify_property_type(None, "AG", None) == "agricultural"

    def test_condo_legal_description(self):
        assert classify_property_type(None, None, "UNIT 5 CONDO") == "residential"

    def test_acreage_legal_description(self):
        assert classify_property_type(None, None, "10 ACREAGE TRACT 5") == "land"

    def test_unknown(self):
        assert classify_property_type(None, None, None) == "unknown"

    def test_land_use_takes_priority(self):
        # Land use code = residential, zoning = commercial → residential wins
        assert classify_property_type("01", "C1", None) == "residential"

    def test_keyword_land_use(self):
        assert classify_property_type("SINGLE FAMILY", None, None) == "residential"
        assert classify_property_type("COMMERCIAL", None, None) == "commercial"


# ═══════════════════════════════════════════════════════════════════════════════
# Agent integration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestParcelResearchAgent:
    @pytest.fixture
    def agent(self):
        with patch("aloha.agents.base.get_agent_model", return_value="test-model"):
            from aloha.agents.parcel_research.agent import ParcelResearchAgent
            return ParcelResearchAgent()

    @pytest.fixture
    def base_context(self):
        return {
            "parcel_id": "123-456-789",
            "state": "FL",
            "county": "orange",
            "address": "123 Main St",
        }

    @pytest.mark.asyncio
    async def test_arcgis_success(self, agent, base_context):
        agent._fetch_assessor_data = AsyncMock(return_value={
            "PARCELNO": "123-456-789",
            "SITEADDR": "123 Main St",
            "ZONING": "RS-1",
            "LANDUSE": "01",
            "ACREAGE": "0.25",
            "ASSESSED": "200000",
        })
        agent._persist = AsyncMock()
        agent._update_status = AsyncMock()

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        agent._persist.assert_called_once()

    @pytest.mark.asyncio
    async def test_assessor_data_unavailable(self, agent, base_context):
        agent._fetch_assessor_data = AsyncMock(return_value={"error": "not found"})
        agent._persist = AsyncMock()
        agent._update_status = AsyncMock()

        result = await agent.run(base_context)

        assert result["status"] == "failed"


# ═══════════════════════════════════════════════════════════════════════════════
# query_assessor_web — County Assessor MCP server integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestQueryAssessorWeb:
    """Tests for query_assessor_web which delegates to CountyAssessorMCPServer."""

    _PATCH_TARGET = (
        "aloha.mcp_servers.county_assessor.server.create_county_assessor_server"
    )

    @pytest.mark.asyncio
    async def test_lookup_parcel_success(self) -> None:
        """Successful lookup via CountyAssessorMCPServer.lookup_parcel."""
        mock_server = MagicMock()
        mock_server.lookup_parcel = AsyncMock(
            return_value={"parcel_id": "123", "address": "456 Main St"},
        )

        with patch(self._PATCH_TARGET, return_value=mock_server):
            result = await query_assessor_web("123", "FL", "orange")

        assert result["parcel_id"] == "123"
        assert result["address"] == "456 Main St"
        mock_server.lookup_parcel.assert_awaited_once_with(
            "123", "FL", "orange",
        )

    @pytest.mark.asyncio
    async def test_lookup_fails_address_fallback_succeeds(self) -> None:
        """When lookup_parcel returns error and address is given, tries
        search_by_address and returns first result."""
        mock_server = MagicMock()
        mock_server.lookup_parcel = AsyncMock(
            return_value={"error": "not found"},
        )
        mock_server.search_by_address = AsyncMock(
            return_value={
                "parcels": [{"parcel_id": "123", "address": "456 Main St"}],
            },
        )

        with patch(self._PATCH_TARGET, return_value=mock_server):
            result = await query_assessor_web(
                "123", "FL", "orange", address="456 Main St",
            )

        assert result["parcel_id"] == "123"
        mock_server.search_by_address.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lookup_fails_no_address_returns_error(self) -> None:
        """When lookup_parcel fails and no address provided, returns the
        error dict from lookup_parcel."""
        mock_server = MagicMock()
        mock_server.lookup_parcel = AsyncMock(
            return_value={"error": "No scraper available for ZZ/nowhere"},
        )

        with patch(self._PATCH_TARGET, return_value=mock_server):
            result = await query_assessor_web("999", "ZZ", "nowhere")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_server_import_error_returns_error(self) -> None:
        """When create_county_assessor_server cannot be imported, returns
        graceful error dict."""
        with patch(self._PATCH_TARGET, side_effect=ImportError("not installed")):
            result = await query_assessor_web("123", "FL", "orange")

        assert "error" in result
        assert result["parcel_id"] == "123"

    @pytest.mark.asyncio
    async def test_server_exception_returns_error(self) -> None:
        """When the MCP server raises an unexpected error, returns graceful
        error dict."""
        mock_server = MagicMock()
        mock_server.lookup_parcel = AsyncMock(
            side_effect=RuntimeError("network down"),
        )

        with patch(self._PATCH_TARGET, return_value=mock_server):
            result = await query_assessor_web("123", "FL", "orange")

        assert "error" in result
        assert "network down" in result["error"]
