"""UCC Filing MCP Server — Cobalt Intelligence API + state scraper cascade.

Exposes tools for searching Uniform Commercial Code filings via the Cobalt
Intelligence API (primary) with fallback to state SOS web scrapers for
states where Cobalt coverage is limited.

Tools exposed:
- search_ucc_filings: search UCC filings by debtor name and state
- get_filing_details: fetch full filing detail by filing number and state

Cobalt Intelligence API docs: https://cobaltintelligence.com/api
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from aloha.mcp_servers.base import BaseMCPServer, ToolDefinition
from aloha.mcp_servers.ucc.providers import CobaltUCCProvider, StateUCCScraper

log = structlog.get_logger().bind(component="ucc_mcp")


class UCCMCPServer(BaseMCPServer):
    """MCP server for UCC filing searches.

    Uses Cobalt Intelligence API as primary provider with state SOS
    scraper fallback for broader coverage.
    """

    def __init__(self, cobalt_api_key: str | None = None) -> None:
        super().__init__(name="ucc")
        self._cobalt_api_key = cobalt_api_key
        self._provider: CobaltUCCProvider | None = None
        self._scraper = StateUCCScraper()
        if cobalt_api_key:
            self._provider = CobaltUCCProvider(cobalt_api_key)
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(ToolDefinition(
            name="search_ucc_filings",
            description=(
                "Search Uniform Commercial Code filings by debtor name and state "
                "using Cobalt Intelligence API with state scraper fallback. "
                "Returns matching filings with secured party and collateral info."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "debtor_name": {
                        "type": "string",
                        "description": "Name of the debtor (person or entity).",
                    },
                    "state": {
                        "type": "string",
                        "description": "Two-letter US state abbreviation.",
                    },
                    "filing_type": {
                        "type": "string",
                        "description": "Optional filter: 'initial', 'amendment', 'continuation'.",
                    },
                },
                "required": ["debtor_name", "state"],
            },
            handler=self.search_ucc_filings,
        ))

        self.register_tool(ToolDefinition(
            name="get_filing_details",
            description=(
                "Fetch full UCC filing details by filing number and state "
                "from Cobalt Intelligence. Returns debtor, secured party, "
                "collateral description, and lapse date."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "filing_number": {
                        "type": "string",
                        "description": "UCC filing number from a prior search.",
                    },
                    "state": {
                        "type": "string",
                        "description": "State where the filing was recorded.",
                    },
                },
                "required": ["filing_number", "state"],
            },
            handler=self.get_filing_details,
        ))

    # ── Tool handlers ─────────────────────────────────────────────────────

    async def search_ucc_filings(
        self,
        debtor_name: str,
        state: str,
        filing_type: str | None = None,
    ) -> dict[str, Any]:
        """Search UCC filings — Cobalt Intelligence then scraper fallback.

        Cascade:
        1. Cobalt Intelligence API (if API key configured)
        2. StateUCCScraper for states with public SOS portals
        """
        filings: list[dict[str, Any]] = []

        # Tier 1: Cobalt Intelligence
        if self._provider:
            try:
                results = await self._provider.search(
                    debtor_name=debtor_name,
                    state=state,
                    filing_type=filing_type,
                )
                filings.extend(_normalise_ucc_filing(r) for r in results)
                log.info(
                    "cobalt_ucc_search_complete",
                    debtor_name=debtor_name,
                    state=state,
                    count=len(results),
                )
            except httpx.HTTPStatusError as exc:
                log.warning(
                    "cobalt_ucc_api_error",
                    status=exc.response.status_code,
                    tool="search_ucc_filings",
                )
            except Exception as exc:
                log.warning("cobalt_ucc_request_failed", error=str(exc))

        # Tier 2: State scraper fallback
        try:
            scraper_results = await self._scraper.search(
                debtor_name=debtor_name,
                state=state,
                filing_type=filing_type,
            )
            filings.extend(_normalise_ucc_filing(r) for r in scraper_results)
        except Exception as exc:
            log.warning("state_ucc_scraper_failed", error=str(exc))

        log.info(
            "search_ucc_filings_complete",
            debtor_name=debtor_name,
            state=state,
            count=len(filings),
        )
        return {"filings": filings}

    async def get_filing_details(
        self,
        filing_number: str,
        state: str,
    ) -> dict[str, Any]:
        """Fetch full UCC filing details from Cobalt Intelligence."""
        if not self._provider:
            log.warning("cobalt_ucc_no_api_key")
            return {"error": "Cobalt Intelligence API key not configured"}

        try:
            data = await self._provider.get_detail(
                filing_number=filing_number,
                state=state,
            )
            if data is None:
                return {"error": f"Filing {filing_number} not found in {state}"}
            log.info(
                "get_filing_details_complete",
                filing_number=filing_number,
                state=state,
            )
            return _normalise_ucc_filing(data)
        except httpx.HTTPStatusError as exc:
            log.warning(
                "cobalt_ucc_api_error",
                status=exc.response.status_code,
                filing_number=filing_number,
            )
            return {"error": f"API error {exc.response.status_code}"}
        except Exception as exc:
            log.error("cobalt_ucc_request_failed", error=str(exc))
            return {"error": str(exc)}

    async def close(self) -> None:
        """Clean up HTTP clients."""
        if self._provider:
            await self._provider.close()


# ── Normalisation helpers ─────────────────────────────────────────────────────

def _normalise_ucc_filing(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a raw UCC filing record to canonical fields."""
    return {
        "filing_number": raw.get("filing_number") or raw.get("file_number"),
        "filing_date": raw.get("filing_date") or raw.get("file_date"),
        "lapse_date": raw.get("lapse_date") or raw.get("expiration_date"),
        "filing_type": raw.get("filing_type") or raw.get("type"),
        "debtor_name": raw.get("debtor_name") or raw.get("debtor"),
        "secured_party": raw.get("secured_party") or raw.get("secured_party_name"),
        "collateral": raw.get("collateral") or raw.get("collateral_description"),
        "state": raw.get("state"),
    }


# ── Factory ───────────────────────────────────────────────────────────────────

def create_ucc_server() -> UCCMCPServer:
    """Build the UCC MCP server from settings.

    The server works without a Cobalt API key (graceful degradation
    to scraper-only mode), but detail lookups require one.
    """
    from aloha.config import settings

    api_key = settings.cobalt_intelligence_api_key
    if not api_key:
        log.warning(
            "cobalt_ucc_api_key_missing",
            msg="UCC server starting without Cobalt Intelligence API key. "
            "Filing search will use scraper-only mode.",
        )
    return UCCMCPServer(cobalt_api_key=api_key)
