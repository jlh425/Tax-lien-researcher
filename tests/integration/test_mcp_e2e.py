"""End-to-end integration tests for MCP servers with real API keys.

These tests hit external APIs and are SKIPPED when the corresponding API
keys are not set in the environment. Run with real keys to verify
integration:

    COURTLISTENER_API_KEY=xxx COBALT_INTELLIGENCE_API_KEY=yyy pytest tests/integration/ -v
"""

from __future__ import annotations

import os

import pytest

# ── Skip markers ─────────────────────────────────────────────────────────────

_HAS_COURTLISTENER_KEY = bool(os.environ.get("COURTLISTENER_API_KEY"))
_HAS_COBALT_KEY = bool(os.environ.get("COBALT_INTELLIGENCE_API_KEY"))
_HAS_GOOGLE_MAPS_KEY = bool(os.environ.get("GOOGLE_MAPS_API_KEY"))

skip_no_courtlistener = pytest.mark.skipif(
    not _HAS_COURTLISTENER_KEY,
    reason="COURTLISTENER_API_KEY not set",
)
skip_no_cobalt = pytest.mark.skipif(
    not _HAS_COBALT_KEY,
    reason="COBALT_INTELLIGENCE_API_KEY not set",
)
skip_no_google_maps = pytest.mark.skipif(
    not _HAS_GOOGLE_MAPS_KEY,
    reason="GOOGLE_MAPS_API_KEY not set",
)


# ═══════════════════════════════════════════════════════════════════════════════
# Court Records MCP Server — CourtListener API
# ═══════════════════════════════════════════════════════════════════════════════


@skip_no_courtlistener
class TestCourtRecordsE2E:
    @pytest.mark.asyncio
    async def test_search_federal_cases(self) -> None:
        from aloha.mcp_servers.court_records.server import CourtRecordsMCPServer

        key = os.environ["COURTLISTENER_API_KEY"]
        server = CourtRecordsMCPServer(courtlistener_api_key=key)
        try:
            result = await server.search_federal_cases("Apple Inc")
            assert "cases" in result
            assert isinstance(result["cases"], list)
            # CourtListener should find some Apple cases
            if result["cases"]:
                case = result["cases"][0]
                assert "case_name" in case or "docket_id" in case
        finally:
            await server.close()

    @pytest.mark.asyncio
    async def test_get_case_details(self) -> None:
        from aloha.mcp_servers.court_records.server import CourtRecordsMCPServer

        key = os.environ["COURTLISTENER_API_KEY"]
        server = CourtRecordsMCPServer(courtlistener_api_key=key)
        try:
            # Search first, then get details of first result
            search = await server.search_federal_cases("Google")
            if search.get("cases"):
                docket_id = search["cases"][0].get("docket_id")
                if docket_id:
                    detail = await server.get_case_details(docket_id)
                    assert "case_name" in detail or "error" in detail
        finally:
            await server.close()

    @pytest.mark.asyncio
    async def test_search_state_liens(self) -> None:
        from aloha.mcp_servers.court_records.server import CourtRecordsMCPServer

        key = os.environ["COURTLISTENER_API_KEY"]
        server = CourtRecordsMCPServer(courtlistener_api_key=key)
        try:
            result = await server.search_state_liens("Smith", state="FL")
            assert "liens" in result or "cases" in result or "error" in result
        finally:
            await server.close()


# ═══════════════════════════════════════════════════════════════════════════════
# UCC MCP Server — Cobalt Intelligence API
# ═══════════════════════════════════════════════════════════════════════════════


@skip_no_cobalt
class TestUCCE2E:
    @pytest.mark.asyncio
    async def test_search_ucc_filings(self) -> None:
        from aloha.mcp_servers.ucc.server import UCCMCPServer

        key = os.environ["COBALT_INTELLIGENCE_API_KEY"]
        server = UCCMCPServer(cobalt_api_key=key)
        try:
            result = await server.search_ucc_filings("Apple Inc", "DE")
            assert "filings" in result or "error" in result
            if "filings" in result:
                assert isinstance(result["filings"], list)
        finally:
            await server.close()

    @pytest.mark.asyncio
    async def test_get_filing_details(self) -> None:
        from aloha.mcp_servers.ucc.server import UCCMCPServer

        key = os.environ["COBALT_INTELLIGENCE_API_KEY"]
        server = UCCMCPServer(cobalt_api_key=key)
        try:
            # Search first, then get detail
            search = await server.search_ucc_filings("Microsoft", "WA")
            if search.get("filings"):
                filing_number = search["filings"][0].get("filing_number")
                if filing_number:
                    detail = await server.get_filing_details(filing_number, "WA")
                    assert "filing_number" in detail or "error" in detail
        finally:
            await server.close()


# ═══════════════════════════════════════════════════════════════════════════════
# GIS MCP Server — Google Maps Geocoding API
# ═══════════════════════════════════════════════════════════════════════════════


@skip_no_google_maps
class TestGISE2E:
    @pytest.mark.asyncio
    async def test_geocode_address(self) -> None:
        from aloha.mcp_servers.gis.server import GISMCPServer

        key = os.environ["GOOGLE_MAPS_API_KEY"]
        server = GISMCPServer(api_key=key)
        try:
            result = await server.geocode_address("1600 Amphitheatre Parkway, Mountain View, CA")
            assert "results" in result
            if result["results"]:
                r = result["results"][0]
                assert r["latitude"] is not None
                assert r["longitude"] is not None
                assert abs(r["latitude"] - 37.42) < 0.1
        finally:
            await server.close()

    @pytest.mark.asyncio
    async def test_reverse_geocode(self) -> None:
        from aloha.mcp_servers.gis.server import GISMCPServer

        key = os.environ["GOOGLE_MAPS_API_KEY"]
        server = GISMCPServer(api_key=key)
        try:
            result = await server.reverse_geocode(28.5383, -81.3792)
            assert "results" in result
            if result["results"]:
                assert "formatted_address" in result["results"][0]
        finally:
            await server.close()
