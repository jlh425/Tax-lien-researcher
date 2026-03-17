"""Secretary of State MCP Server — Cobalt Intelligence API integration.

Exposes tools for querying entity records from all 50 US state SOS databases
via the Cobalt Intelligence API.  Used by the Entity Research Agent to pierce
LLC/trust/corp ownership structures.

Tools exposed:
- sos_lookup_entity: search by entity name and state
- sos_get_entity_details: fetch full filing detail by entity ID
- sos_search_by_registered_agent: find all entities with a given registered agent
- sos_search_by_address: find entities registered at a given address

Cobalt Intelligence API docs: https://cobaltintelligence.com/api
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from aloha.mcp_servers.base import BaseMCPServer, ToolDefinition

log = structlog.get_logger().bind(component="sos_mcp")

_COBALT_BASE_URL = "https://api.cobaltintelligence.com/v1"
_TIMEOUT = 30.0


class SOSMCPServer(BaseMCPServer):
    """MCP server wrapping the Cobalt Intelligence Secretary of State API."""

    def __init__(self, api_key: str) -> None:
        super().__init__(name="sos")
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(ToolDefinition(
            name="sos_lookup_entity",
            description=(
                "Search for a business entity by name and state using Cobalt Intelligence. "
                "Returns a list of matching entities with basic filing information."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "entity_name": {
                        "type": "string",
                        "description": "Business entity name to search for.",
                    },
                    "state": {
                        "type": "string",
                        "description": "Two-letter US state abbreviation (e.g. 'FL', 'TX').",
                    },
                    "entity_type": {
                        "type": "string",
                        "description": "Optional filter: 'llc', 'corporation', 'lp', etc.",
                    },
                },
                "required": ["entity_name", "state"],
            },
            handler=self.sos_lookup_entity,
        ))

        self.register_tool(ToolDefinition(
            name="sos_get_entity_details",
            description=(
                "Fetch full SOS filing details for an entity by its Cobalt entity ID. "
                "Returns officers, registered agent, formation date, status, and filing URL."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "Cobalt Intelligence entity ID from a prior search.",
                    },
                    "state": {
                        "type": "string",
                        "description": "State where the entity is filed.",
                    },
                },
                "required": ["entity_id", "state"],
            },
            handler=self.sos_get_entity_details,
        ))

        self.register_tool(ToolDefinition(
            name="sos_search_by_registered_agent",
            description=(
                "Find all entities sharing a registered agent in a given state. "
                "Useful for detecting shell company networks."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "Registered agent name to search for.",
                    },
                    "state": {
                        "type": "string",
                        "description": "Two-letter US state abbreviation.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 50).",
                    },
                },
                "required": ["agent_name", "state"],
            },
            handler=self.sos_search_by_registered_agent,
        ))

        self.register_tool(ToolDefinition(
            name="sos_search_by_address",
            description=(
                "Find all entities registered at a given address in a state. "
                "Detects shell company networks sharing a registered address."
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
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 50).",
                    },
                },
                "required": ["address", "state"],
            },
            handler=self.sos_search_by_address,
        ))

    # ── HTTP client ───────────────────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=_COBALT_BASE_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=httpx.Timeout(_TIMEOUT),
            )
        return self._client

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a GET request to the Cobalt API."""
        client = await self._get_client()
        log.debug("cobalt_api_request", path=path, params=params)
        response = await client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ── Tool handlers ─────────────────────────────────────────────────────

    async def sos_lookup_entity(
        self,
        entity_name: str,
        state: str,
        entity_type: str | None = None,
    ) -> dict[str, Any]:
        """Search Cobalt Intelligence for a business entity by name.

        Returns list of matching entities with name, status, entity_id, and
        formation date.
        """
        params: dict[str, Any] = {
            "name": entity_name,
            "state": state.upper(),
        }
        if entity_type:
            params["type"] = entity_type

        try:
            data = await self._get("/entities/search", params=params)
            entities = data.get("entities", data.get("results", []))
            log.info("sos_search_complete", entity_name=entity_name, state=state, count=len(entities))
            return {"entities": [_normalise_entity_stub(e) for e in entities]}
        except httpx.HTTPStatusError as exc:
            log.warning("cobalt_api_error", status=exc.response.status_code, path="/entities/search")
            return {"error": f"API error {exc.response.status_code}", "entities": []}
        except Exception as exc:
            log.error("cobalt_request_failed", error=str(exc))
            return {"error": str(exc), "entities": []}

    async def sos_get_entity_details(
        self,
        entity_id: str,
        state: str,
    ) -> dict[str, Any]:
        """Fetch full SOS filing details for a specific entity.

        Returns officers, registered agent, formation date, status, and
        filing URLs.
        """
        try:
            data = await self._get(f"/entities/{entity_id}", params={"state": state.upper()})
            log.info("sos_entity_detail_fetched", entity_id=entity_id, state=state)
            return _normalise_entity_detail(data)
        except httpx.HTTPStatusError as exc:
            log.warning("cobalt_api_error", status=exc.response.status_code, entity_id=entity_id)
            return {"error": f"API error {exc.response.status_code}"}
        except Exception as exc:
            log.error("cobalt_request_failed", error=str(exc))
            return {"error": str(exc)}

    async def sos_search_by_registered_agent(
        self,
        agent_name: str,
        state: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Find entities sharing a registered agent — shell network detection."""
        params: dict[str, Any] = {
            "registered_agent": agent_name,
            "state": state.upper(),
            "limit": limit,
        }
        try:
            data = await self._get("/entities/search", params=params)
            entities = data.get("entities", data.get("results", []))
            log.info(
                "sos_agent_search_complete",
                agent_name=agent_name,
                state=state,
                count=len(entities),
            )
            return {"entities": [_normalise_entity_stub(e) for e in entities]}
        except httpx.HTTPStatusError as exc:
            log.warning("cobalt_api_error", status=exc.response.status_code)
            return {"error": f"API error {exc.response.status_code}", "entities": []}
        except Exception as exc:
            log.error("cobalt_request_failed", error=str(exc))
            return {"error": str(exc), "entities": []}

    async def sos_search_by_address(
        self,
        address: str,
        state: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Find entities registered at a given address — shell network detection."""
        params: dict[str, Any] = {
            "address": address,
            "state": state.upper(),
            "limit": limit,
        }
        try:
            data = await self._get("/entities/search", params=params)
            entities = data.get("entities", data.get("results", []))
            log.info(
                "sos_address_search_complete",
                address=address,
                state=state,
                count=len(entities),
            )
            return {"entities": [_normalise_entity_stub(e) for e in entities]}
        except httpx.HTTPStatusError as exc:
            log.warning("cobalt_api_error", status=exc.response.status_code)
            return {"error": f"API error {exc.response.status_code}", "entities": []}
        except Exception as exc:
            log.error("cobalt_request_failed", error=str(exc))
            return {"error": str(exc), "entities": []}


# ── Normalisation helpers ─────────────────────────────────────────────────────

def _normalise_entity_stub(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a Cobalt search result row to canonical fields."""
    return {
        "entity_id": raw.get("id") or raw.get("entity_id"),
        "entity_name": raw.get("name") or raw.get("entity_name"),
        "entity_type": raw.get("type") or raw.get("entity_type"),
        "state": raw.get("state"),
        "status": raw.get("status") or raw.get("sos_status"),
        "formation_date": raw.get("formation_date") or raw.get("filed_date"),
    }


def _normalise_entity_detail(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a Cobalt entity detail response to canonical fields."""
    officers_raw = raw.get("officers") or raw.get("principals") or []
    officers = [
        {
            "name": o.get("name"),
            "title": o.get("title") or o.get("role"),
            "address": o.get("address"),
        }
        for o in officers_raw
    ]

    members_raw = raw.get("members") or raw.get("managers") or []
    members = [
        {
            "name": m.get("name"),
            "title": m.get("title") or m.get("role", "Member"),
            "address": m.get("address"),
        }
        for m in members_raw
    ]

    agent_raw = raw.get("registered_agent") or {}
    if isinstance(agent_raw, str):
        agent_name = agent_raw
        agent_address = None
    else:
        agent_name = agent_raw.get("name")
        agent_address = agent_raw.get("address")

    return {
        "entity_id": raw.get("id") or raw.get("entity_id"),
        "entity_name": raw.get("name") or raw.get("entity_name"),
        "entity_type": raw.get("type") or raw.get("entity_type"),
        "state": raw.get("state"),
        "status": raw.get("status"),
        "formation_date": raw.get("formation_date") or raw.get("filed_date"),
        "registered_agent": agent_name,
        "registered_agent_address": agent_address,
        "officers": officers,
        "managers_members": members,
        "sos_filing_url": raw.get("filing_url") or raw.get("source_url"),
        "raw": raw,  # kept for full-field access by entity research agent
    }


# ── Factory ───────────────────────────────────────────────────────────────────

def create_sos_server() -> SOSMCPServer:
    """Build the SOS MCP server from settings.

    Raises:
        ValueError: If ``COBALT_INTELLIGENCE_API_KEY`` is not configured.
    """
    from aloha.config import settings

    api_key = settings.cobalt_intelligence_api_key
    if not api_key:
        raise ValueError(
            "COBALT_INTELLIGENCE_API_KEY is required to use the SOS MCP server. "
            "Get your key at https://cobaltintelligence.com."
        )
    return SOSMCPServer(api_key=api_key)
