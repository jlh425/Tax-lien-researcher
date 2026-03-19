"""Court Records MCP Server — federal case and state lien lookups.

Stub implementation that defines canonical output shapes so agents can
integrate now.  Real API backends (PACER, state lien databases) will be
wired in when vendor contracts are finalised.

Tools exposed:
- search_federal_cases: search federal court cases by party name
- search_state_liens: search state-level lien filings
- get_case_details: fetch full case detail by case ID
"""

from __future__ import annotations

from typing import Any

import structlog

from aloha.mcp_servers.base import BaseMCPServer, ToolDefinition

log = structlog.get_logger().bind(component="court_records_mcp")


class CourtRecordsMCPServer(BaseMCPServer):
    """MCP server for court records and lien searches (stub)."""

    def __init__(self) -> None:
        super().__init__(name="court_records")
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(ToolDefinition(
            name="search_federal_cases",
            description=(
                "Search federal court cases by party name, state, and case type. "
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
        ))

        self.register_tool(ToolDefinition(
            name="search_state_liens",
            description=(
                "Search state-level lien filings (tax liens, judgment liens, "
                "mechanic's liens) by debtor name and state."
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
        ))

        self.register_tool(ToolDefinition(
            name="get_case_details",
            description=(
                "Fetch full case details by case ID. Returns parties, docket "
                "entries, filing dates, and case status."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "case_id": {
                        "type": "string",
                        "description": "Court case identifier from a prior search.",
                    },
                },
                "required": ["case_id"],
            },
            handler=self.get_case_details,
        ))

    # -- Tool handlers ---------------------------------------------------------

    async def search_federal_cases(
        self,
        party_name: str,
        state: str | None = None,
        case_type: str | None = None,
    ) -> dict[str, Any]:
        """Search federal court cases (stub)."""
        log.info(
            "search_federal_cases_stub",
            party_name=party_name,
            state=state,
            case_type=case_type,
        )
        return {"stub": True, "cases": [], "query": {
            "party_name": party_name,
            "state": state,
            "case_type": case_type,
        }}

    async def search_state_liens(
        self,
        debtor_name: str,
        state: str,
        lien_type: str | None = None,
    ) -> dict[str, Any]:
        """Search state lien filings (stub)."""
        log.info(
            "search_state_liens_stub",
            debtor_name=debtor_name,
            state=state,
            lien_type=lien_type,
        )
        return {"stub": True, "liens": [], "query": {
            "debtor_name": debtor_name,
            "state": state,
            "lien_type": lien_type,
        }}

    async def get_case_details(
        self,
        case_id: str,
    ) -> dict[str, Any]:
        """Fetch full case details (stub)."""
        log.info("get_case_details_stub", case_id=case_id)
        return {"stub": True, "case_id": case_id, "detail": None}


# -- Normalisation helpers -----------------------------------------------------

def _normalise_case(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a raw court case record to canonical fields."""
    return {
        "case_id": raw.get("case_id") or raw.get("id"),
        "case_title": raw.get("case_title") or raw.get("title"),
        "court": raw.get("court") or raw.get("court_name"),
        "case_type": raw.get("case_type") or raw.get("type"),
        "filing_date": raw.get("filing_date") or raw.get("filed_date"),
        "status": raw.get("status") or raw.get("case_status"),
        "parties": raw.get("parties", []),
    }


def _normalise_lien(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a raw lien record to canonical fields."""
    return {
        "filing_number": raw.get("filing_number") or raw.get("instrument_number"),
        "debtor": raw.get("debtor") or raw.get("debtor_name"),
        "creditor": raw.get("creditor") or raw.get("creditor_name"),
        "amount": raw.get("amount") or raw.get("lien_amount"),
        "filing_date": raw.get("filing_date") or raw.get("recorded_date"),
        "state": raw.get("state"),
    }


# -- Factory -------------------------------------------------------------------

def create_court_records_server() -> CourtRecordsMCPServer:
    """Build the Court Records MCP server.

    No API keys required (stub implementation).
    """
    return CourtRecordsMCPServer()
