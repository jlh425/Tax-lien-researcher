"""UCC Filing MCP Server — Uniform Commercial Code filing searches.

Stub implementation that defines canonical output shapes so agents can
integrate now.  Real API backends (state SOS UCC portals) will be wired
in when scraper implementations are ready.

Tools exposed:
- search_ucc_filings: search UCC filings by debtor name and state
- get_filing_details: fetch full filing detail by filing number
"""

from __future__ import annotations

from typing import Any

import structlog

from aloha.mcp_servers.base import BaseMCPServer, ToolDefinition

log = structlog.get_logger().bind(component="ucc_mcp")


class UCCMCPServer(BaseMCPServer):
    """MCP server for UCC filing searches (stub)."""

    def __init__(self) -> None:
        super().__init__(name="ucc")
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(ToolDefinition(
            name="search_ucc_filings",
            description=(
                "Search Uniform Commercial Code filings by debtor name and state. "
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
                "Fetch full UCC filing details by filing number and state. "
                "Returns debtor, secured party, collateral description, and lapse date."
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

    # -- Tool handlers ---------------------------------------------------------

    async def search_ucc_filings(
        self,
        debtor_name: str,
        state: str,
        filing_type: str | None = None,
    ) -> dict[str, Any]:
        """Search UCC filings (stub)."""
        log.info(
            "search_ucc_filings_stub",
            debtor_name=debtor_name,
            state=state,
            filing_type=filing_type,
        )
        return {"stub": True, "filings": [], "query": {
            "debtor_name": debtor_name,
            "state": state,
            "filing_type": filing_type,
        }}

    async def get_filing_details(
        self,
        filing_number: str,
        state: str,
    ) -> dict[str, Any]:
        """Fetch full UCC filing details (stub)."""
        log.info("get_filing_details_stub", filing_number=filing_number, state=state)
        return {"stub": True, "filing_number": filing_number, "state": state, "detail": None}


# -- Normalisation helpers -----------------------------------------------------

def _normalise_ucc_filing(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a raw UCC filing record to canonical fields."""
    return {
        "filing_number": raw.get("filing_number") or raw.get("file_number"),
        "filing_date": raw.get("filing_date") or raw.get("file_date"),
        "lapse_date": raw.get("lapse_date") or raw.get("expiration_date"),
        "debtor_name": raw.get("debtor_name") or raw.get("debtor"),
        "secured_party": raw.get("secured_party") or raw.get("secured_party_name"),
        "collateral": raw.get("collateral") or raw.get("collateral_description"),
    }


# -- Factory -------------------------------------------------------------------

def create_ucc_server() -> UCCMCPServer:
    """Build the UCC MCP server.

    No API keys required (stub implementation).
    """
    return UCCMCPServer()
