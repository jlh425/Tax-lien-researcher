"""Court Records MCP Server — CourtListener API + state lien scraper cascade.

Exposes tools for querying federal court dockets via the CourtListener REST
API v4 (free tier, RECAP archive) and state-level lien records via a
Playwright scraper fallback.

Tools exposed:
- search_federal_cases: search federal court cases by party name
- search_state_liens: search state-level lien filings
- get_case_details: fetch full case detail by docket ID

CourtListener API docs: https://www.courtlistener.com/help/api/rest/
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from aloha.mcp_servers.base import BaseMCPServer, ToolDefinition
from aloha.mcp_servers.court_records.providers import (
    CourtListenerProvider,
    StateLienScraper,
)

log = structlog.get_logger().bind(component="court_records_mcp")


class CourtRecordsMCPServer(BaseMCPServer):
    """MCP server for court records and lien searches.

    Uses CourtListener REST API v4 for federal case data and a state
    scraper cascade for lien records.
    """

    def __init__(self, courtlistener_api_key: str | None = None) -> None:
        super().__init__(name="court_records")
        self._courtlistener_api_key = courtlistener_api_key
        self._provider: CourtListenerProvider | None = None
        self._lien_scraper = StateLienScraper()
        if courtlistener_api_key:
            self._provider = CourtListenerProvider(courtlistener_api_key)
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(
            ToolDefinition(
                name="search_federal_cases",
                description=(
                    "Search federal court cases by party name, state, and case type "
                    "using CourtListener RECAP docket data. "
                    "Returns matching cases with basic filing information."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "party_name": {
                            "type": "string",
                            "description": "Name of a party (plaintiff or defendant).",
                        },
                        "state": {
                            "type": "string",
                            "description": "Two-letter US state abbreviation to narrow search.",
                        },
                        "case_type": {
                            "type": "string",
                            "description": "Optional filter: 'civil', 'bankruptcy', 'criminal'.",
                        },
                    },
                    "required": ["party_name"],
                },
                handler=self.search_federal_cases,
            )
        )

        self.register_tool(
            ToolDefinition(
                name="search_state_liens",
                description=(
                    "Search state-level lien filings (tax liens, judgment liens, "
                    "mechanic's liens) by debtor name and state. Uses CourtListener "
                    "filtered search with state scraper fallback."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "debtor_name": {
                            "type": "string",
                            "description": "Name of the debtor to search for.",
                        },
                        "state": {
                            "type": "string",
                            "description": "Two-letter US state abbreviation.",
                        },
                        "lien_type": {
                            "type": "string",
                            "description": "Optional filter: 'tax', 'judgment', 'mechanics'.",
                        },
                    },
                    "required": ["debtor_name", "state"],
                },
                handler=self.search_state_liens,
            )
        )

        self.register_tool(
            ToolDefinition(
                name="get_case_details",
                description=(
                    "Fetch full case details by docket ID from CourtListener. "
                    "Returns parties, docket entries, filing dates, and case status."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {
                            "type": "string",
                            "description": "CourtListener docket ID from a prior search.",
                        },
                    },
                    "required": ["case_id"],
                },
                handler=self.get_case_details,
            )
        )

    # ── Tool handlers ─────────────────────────────────────────────────────

    async def search_federal_cases(
        self,
        party_name: str,
        state: str | None = None,
        case_type: str | None = None,
    ) -> dict[str, Any]:
        """Search federal court cases via CourtListener RECAP dockets."""
        if not self._provider:
            log.warning("courtlistener_no_api_key")
            return {
                "error": "CourtListener API key not configured",
                "cases": [],
            }

        try:
            results = await self._provider.search(
                party_name=party_name,
                state=state,
                case_type=case_type,
            )
            cases = [_normalise_case(r) for r in results]
            log.info(
                "search_federal_cases_complete",
                party_name=party_name,
                state=state,
                count=len(cases),
            )
            return {"cases": cases}
        except httpx.HTTPStatusError as exc:
            log.warning(
                "courtlistener_api_error",
                status=exc.response.status_code,
                tool="search_federal_cases",
            )
            return {"error": f"API error {exc.response.status_code}", "cases": []}
        except Exception as exc:
            log.error("courtlistener_request_failed", error=str(exc))
            return {"error": str(exc), "cases": []}

    async def get_case_details(
        self,
        case_id: str,
    ) -> dict[str, Any]:
        """Fetch full case details from CourtListener by docket ID."""
        if not self._provider:
            log.warning("courtlistener_no_api_key")
            return {"error": "CourtListener API key not configured"}

        try:
            data = await self._provider.get_detail(case_id)
            if data is None:
                return {"error": f"Docket {case_id} not found"}
            log.info("get_case_details_complete", case_id=case_id)
            return _normalise_case(data)
        except httpx.HTTPStatusError as exc:
            log.warning(
                "courtlistener_api_error",
                status=exc.response.status_code,
                case_id=case_id,
            )
            return {"error": f"API error {exc.response.status_code}"}
        except Exception as exc:
            log.error("courtlistener_request_failed", error=str(exc))
            return {"error": str(exc)}

    async def search_state_liens(
        self,
        debtor_name: str,
        state: str,
        lien_type: str | None = None,
    ) -> dict[str, Any]:
        """Search state lien filings — CourtListener then scraper fallback.

        Cascade:
        1. CourtListener search filtered by state court type
        2. StateLienScraper for states with public portals
        """
        liens: list[dict[str, Any]] = []

        # Tier 1: CourtListener (if API key available)
        if self._provider:
            try:
                results = await self._provider.search(
                    party_name=debtor_name,
                    state=state,
                )
                liens.extend(_normalise_lien(r) for r in results)
            except httpx.HTTPStatusError as exc:
                log.warning(
                    "courtlistener_lien_search_error",
                    status=exc.response.status_code,
                )
            except Exception as exc:
                log.warning("courtlistener_lien_search_failed", error=str(exc))

        # Tier 2: State scraper fallback
        try:
            scraper_results = await self._lien_scraper.search(
                debtor_name=debtor_name,
                state=state,
                lien_type=lien_type,
            )
            liens.extend(_normalise_lien(r) for r in scraper_results)
        except Exception as exc:
            log.warning("state_lien_scraper_failed", error=str(exc))

        log.info(
            "search_state_liens_complete",
            debtor_name=debtor_name,
            state=state,
            count=len(liens),
        )
        return {"liens": liens}

    async def close(self) -> None:
        """Clean up HTTP clients."""
        if self._provider:
            await self._provider.close()


# ── Normalisation helpers ─────────────────────────────────────────────────────


def _normalise_case(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a CourtListener docket/search result to canonical fields."""
    # CourtListener search results use caseName; detail uses case_name
    parties_raw = raw.get("parties", [])
    parties = (
        [
            {
                "name": p.get("name") or p.get("party_name"),
                "role": p.get("role") or p.get("party_type"),
            }
            for p in parties_raw
        ]
        if isinstance(parties_raw, list)
        else []
    )

    return {
        "case_id": str(raw.get("docket_id") or raw.get("id") or raw.get("case_id")),
        "case_title": (
            raw.get("caseName")
            or raw.get("case_name")
            or raw.get("case_title")
            or raw.get("title")
        ),
        "court": raw.get("court") or raw.get("court_name") or raw.get("court_id"),
        "case_type": raw.get("case_type") or raw.get("type"),
        "filing_date": (
            raw.get("dateFiled")
            or raw.get("date_filed")
            or raw.get("filing_date")
            or raw.get("filed_date")
        ),
        "status": raw.get("status") or raw.get("case_status"),
        "parties": parties,
        "docket_url": raw.get("absolute_url"),
    }


def _normalise_lien(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a raw lien record to canonical fields."""
    return {
        "filing_number": raw.get("filing_number") or raw.get("instrument_number"),
        "debtor": raw.get("debtor") or raw.get("debtor_name"),
        "creditor": raw.get("creditor") or raw.get("creditor_name"),
        "amount": raw.get("amount") or raw.get("lien_amount"),
        "filing_date": (
            raw.get("filing_date")
            or raw.get("recorded_date")
            or raw.get("dateFiled")
            or raw.get("date_filed")
        ),
        "lien_type": raw.get("lien_type") or raw.get("type"),
        "state": raw.get("state"),
    }


# ── Factory ───────────────────────────────────────────────────────────────────


def create_court_records_server() -> CourtRecordsMCPServer:
    """Build the Court Records MCP server from settings.

    The server works without a CourtListener API key (graceful degradation
    to scraper-only mode), but federal case search requires one.
    """
    from aloha.config import settings

    api_key = settings.courtlistener_api_key
    if not api_key:
        log.warning(
            "courtlistener_api_key_missing",
            msg="Court records server starting without CourtListener API key. "
            "Federal case search will be unavailable. "
            "Get a free key at https://www.courtlistener.com/help/api/",
        )
    return CourtRecordsMCPServer(courtlistener_api_key=api_key)
