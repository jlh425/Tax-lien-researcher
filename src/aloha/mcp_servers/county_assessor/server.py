"""County Assessor MCP Server — parcel data via ArcGIS / QPublic / Tyler.

Delegates to existing Tier 1/2 scrapers with a cascade fallback strategy:
ArcGIS REST API → qPublic JSON/Playwright → Tyler EagleWeb Playwright.

Tools exposed:
- lookup_parcel: look up a parcel by APN, state, and county
- search_by_address: search parcels by street address
- search_by_owner: search parcels by owner name (stub)
"""

from __future__ import annotations

from typing import Any

import structlog

from aloha.mcp_servers.base import BaseMCPServer, ToolDefinition

log = structlog.get_logger().bind(component="county_assessor_mcp")


class CountyAssessorMCPServer(BaseMCPServer):
    """MCP server wrapping county assessor scrapers."""

    def __init__(self) -> None:
        super().__init__(name="county_assessor")
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(ToolDefinition(
            name="lookup_parcel",
            description=(
                "Look up a parcel by APN (assessor parcel number), state, and county. "
                "Cascades through ArcGIS → qPublic → Tyler EagleWeb scrapers."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "parcel_id": {
                        "type": "string",
                        "description": "Assessor parcel number / APN.",
                    },
                    "state": {
                        "type": "string",
                        "description": "Two-letter US state abbreviation.",
                    },
                    "county": {
                        "type": "string",
                        "description": "County name (case-insensitive).",
                    },
                },
                "required": ["parcel_id", "state", "county"],
            },
            handler=self.lookup_parcel,
        ))

        self.register_tool(ToolDefinition(
            name="search_by_address",
            description=(
                "Search for parcels by street address using ArcGIS. "
                "Returns up to 5 matching parcels."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Street address to search for.",
                    },
                    "state": {
                        "type": "string",
                        "description": "Two-letter US state abbreviation.",
                    },
                    "county": {
                        "type": "string",
                        "description": "County name (case-insensitive).",
                    },
                },
                "required": ["address", "state", "county"],
            },
            handler=self.search_by_address,
        ))

        self.register_tool(ToolDefinition(
            name="search_by_owner",
            description=(
                "Search for parcels by owner name (stub — scrapers don't yet "
                "support owner-name search)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "owner_name": {
                        "type": "string",
                        "description": "Property owner name to search for.",
                    },
                    "state": {
                        "type": "string",
                        "description": "Two-letter US state abbreviation.",
                    },
                    "county": {
                        "type": "string",
                        "description": "County name (case-insensitive).",
                    },
                },
                "required": ["owner_name", "state", "county"],
            },
            handler=self.search_by_owner,
        ))

    # -- Tool handlers ---------------------------------------------------------

    async def lookup_parcel(
        self,
        parcel_id: str,
        state: str,
        county: str,
    ) -> dict[str, Any]:
        """Cascade through available scrapers to look up a parcel by APN."""
        key = (state.upper(), county.lower())

        # Tier 1: ArcGIS REST API
        result = await self._try_arcgis(parcel_id, key)
        if result and "error" not in result:
            return result

        # Tier 2a: qPublic
        result = await self._try_qpublic(parcel_id, key)
        if result:
            return result

        # Tier 2b: Tyler EagleWeb
        result = await self._try_tyler(parcel_id, key)
        if result:
            return result

        return {"error": f"No scraper available for {state}/{county}", "parcel_id": parcel_id}

    async def search_by_address(
        self,
        address: str,
        state: str,
        county: str,
    ) -> dict[str, Any]:
        """Search parcels by address via ArcGIS."""
        from aloha.agents.parcel_research.tools import _ARCGIS_ENDPOINTS
        from aloha.scrapers.tier1_apis.arcgis import ArcGISParcelScraper

        key = (state.upper(), county.lower())
        service_url = _ARCGIS_ENDPOINTS.get(key)
        if not service_url:
            return {"error": f"No ArcGIS endpoint for {state}/{county}", "parcels": []}

        scraper = ArcGISParcelScraper(service_url=service_url)
        try:
            results = await scraper.query_by_address(address)
            log.info("address_search_complete", address=address, count=len(results))
            return {"parcels": results}
        except Exception as exc:
            log.warning("address_search_failed", address=address, error=str(exc))
            return {"error": str(exc), "parcels": []}
        finally:
            await scraper.close()

    async def search_by_owner(
        self,
        owner_name: str,
        state: str,
        county: str,
    ) -> dict[str, Any]:
        """Search parcels by owner name (stub)."""
        log.info("search_by_owner_stub", owner_name=owner_name, state=state, county=county)
        return {
            "stub": True,
            "parcels": [],
            "query": {"owner_name": owner_name, "state": state, "county": county},
        }

    # -- Scraper dispatch helpers ----------------------------------------------

    async def _try_arcgis(
        self, parcel_id: str, key: tuple[str, str]
    ) -> dict[str, Any] | None:
        """Try ArcGIS REST API for the given state/county."""
        from aloha.agents.parcel_research.tools import _ARCGIS_ENDPOINTS
        from aloha.scrapers.tier1_apis.arcgis import ArcGISParcelScraper

        service_url = _ARCGIS_ENDPOINTS.get(key)
        if not service_url:
            return None

        scraper = ArcGISParcelScraper(service_url=service_url)
        try:
            result = await scraper.query_by_apn(parcel_id)
            if result:
                log.info("arcgis_parcel_found", parcel_id=parcel_id)
                return result
        except Exception as exc:
            log.warning("arcgis_query_failed", parcel_id=parcel_id, error=str(exc))
        finally:
            await scraper.close()
        return None

    async def _try_qpublic(
        self, parcel_id: str, key: tuple[str, str]
    ) -> dict[str, Any] | None:
        """Try qPublic scraper for the given state/county."""
        from aloha.scrapers.tier2_vendors.qpublic import get_qpublic_scraper

        scraper = get_qpublic_scraper(key[0], key[1])
        if not scraper:
            return None

        try:
            result = await scraper.query_by_apn(parcel_id)
            if result:
                log.info("qpublic_parcel_found", parcel_id=parcel_id)
                return result
        except Exception as exc:
            log.warning("qpublic_query_failed", parcel_id=parcel_id, error=str(exc))
        return None

    async def _try_tyler(
        self, parcel_id: str, key: tuple[str, str]
    ) -> dict[str, Any] | None:
        """Try Tyler EagleWeb scraper for the given state/county."""
        from aloha.scrapers.tier2_vendors.tyler import get_eagleweb_scraper

        scraper = get_eagleweb_scraper(key[0], key[1])
        if not scraper:
            return None

        try:
            result = await scraper.query_by_apn(parcel_id)
            if result:
                log.info("tyler_parcel_found", parcel_id=parcel_id)
                return result
        except Exception as exc:
            log.warning("tyler_query_failed", parcel_id=parcel_id, error=str(exc))
        return None


# -- Factory -------------------------------------------------------------------

def create_county_assessor_server() -> CountyAssessorMCPServer:
    """Build the County Assessor MCP server.

    No API keys required — delegates to existing scrapers.
    """
    return CountyAssessorMCPServer()
