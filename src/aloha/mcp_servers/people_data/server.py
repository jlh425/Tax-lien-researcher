"""People Data MCP Server — PDL + Hunter.io contact enrichment.

Combines People Data Labs (person enrichment, phone search) with Hunter.io
(email verification) behind a single MCP server with one shared HTTP client.

Tools exposed:
- enrich_person: enrich a person record via People Data Labs
- verify_email: verify an email address via Hunter.io
- search_phone: search for a person by phone number via PDL
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from aloha.mcp_servers.base import BaseMCPServer, ToolDefinition

log = structlog.get_logger().bind(component="people_data_mcp")

_PDL_BASE_URL = "https://api.peopledatalabs.com/v5"
_HUNTER_BASE_URL = "https://api.hunter.io/v2"
_TIMEOUT = 20.0


class PeopleDataMCPServer(BaseMCPServer):
    """MCP server combining PDL and Hunter.io APIs."""

    def __init__(self, pdl_api_key: str, hunter_api_key: str) -> None:
        super().__init__(name="people_data")
        self._pdl_api_key = pdl_api_key
        self._hunter_api_key = hunter_api_key
        self._client: httpx.AsyncClient | None = None
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(ToolDefinition(
            name="enrich_person",
            description=(
                "Enrich a person record using People Data Labs. Provide a name "
                "and optionally a location or company to get contact details, "
                "employment history, and social profiles."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Full name of the person.",
                    },
                    "location": {
                        "type": "string",
                        "description": "City, state, or full address (optional).",
                    },
                    "company": {
                        "type": "string",
                        "description": "Current or recent employer (optional).",
                    },
                },
                "required": ["name"],
            },
            handler=self.enrich_person,
        ))

        self.register_tool(ToolDefinition(
            name="verify_email",
            description=(
                "Verify an email address using Hunter.io. Returns deliverability "
                "status, score, and whether the address is disposable."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "Email address to verify.",
                    },
                },
                "required": ["email"],
            },
            handler=self.verify_email,
        ))

        self.register_tool(ToolDefinition(
            name="search_phone",
            description=(
                "Search for a person by phone number using People Data Labs. "
                "Returns matching person records with contact information."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": "Phone number (E.164 format preferred, e.g. '+14155551234').",
                    },
                },
                "required": ["phone"],
            },
            handler=self.search_phone,
        ))

    # -- HTTP client -----------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(_TIMEOUT))
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # -- Tool handlers ---------------------------------------------------------

    async def enrich_person(
        self,
        name: str,
        location: str | None = None,
        company: str | None = None,
    ) -> dict[str, Any]:
        """Enrich a person record via PDL."""
        params: dict[str, str] = {
            "api_key": self._pdl_api_key,
            "name": name,
        }
        if location:
            params["location"] = location
        if company:
            params["company"] = company

        try:
            client = await self._get_client()
            response = await client.get(f"{_PDL_BASE_URL}/person/enrich", params=params)
            response.raise_for_status()
            data = response.json()
            log.info("pdl_enrich_complete", name=name)
            return _normalise_pdl_person(data)
        except httpx.HTTPStatusError as exc:
            log.warning("pdl_api_error", status=exc.response.status_code)
            return {"error": f"PDL API error {exc.response.status_code}"}
        except Exception as exc:
            log.error("pdl_enrich_failed", error=str(exc))
            return {"error": str(exc)}

    async def verify_email(self, email: str) -> dict[str, Any]:
        """Verify an email address via Hunter.io."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{_HUNTER_BASE_URL}/email-verifier",
                params={"email": email, "api_key": self._hunter_api_key},
            )
            response.raise_for_status()
            data = response.json()
            log.info("hunter_verify_complete", email=email)
            return _normalise_hunter_verification(data)
        except httpx.HTTPStatusError as exc:
            log.warning("hunter_api_error", status=exc.response.status_code)
            return {"error": f"Hunter API error {exc.response.status_code}"}
        except Exception as exc:
            log.error("hunter_verify_failed", error=str(exc))
            return {"error": str(exc)}

    async def search_phone(self, phone: str) -> dict[str, Any]:
        """Search for a person by phone number via PDL."""
        try:
            client = await self._get_client()
            response = await client.post(
                f"{_PDL_BASE_URL}/person/search",
                headers={"X-Api-Key": self._pdl_api_key, "Content-Type": "application/json"},
                json={
                    "query": {
                        "bool": {
                            "must": [{"term": {"phone_numbers": phone}}],
                        },
                    },
                    "size": 5,
                },
            )
            response.raise_for_status()
            data = response.json()
            persons = [_normalise_pdl_person(p) for p in data.get("data", [])]
            log.info("pdl_phone_search_complete", phone=phone, count=len(persons))
            return {"persons": persons}
        except httpx.HTTPStatusError as exc:
            log.warning("pdl_api_error", status=exc.response.status_code)
            return {"error": f"PDL API error {exc.response.status_code}", "persons": []}
        except Exception as exc:
            log.error("pdl_phone_search_failed", error=str(exc))
            return {"error": str(exc), "persons": []}


# -- Normalisation helpers -----------------------------------------------------

def _normalise_pdl_person(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a PDL person response to canonical fields."""
    return {
        "full_name": raw.get("full_name"),
        "first_name": raw.get("first_name"),
        "last_name": raw.get("last_name"),
        "emails": raw.get("emails") or [],
        "phone_numbers": raw.get("phone_numbers") or [],
        "linkedin_url": raw.get("linkedin_url"),
        "location": raw.get("location_name") or raw.get("location"),
        "company": raw.get("job_company_name"),
        "title": raw.get("job_title"),
    }


def _normalise_hunter_verification(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a Hunter.io verification response to canonical fields."""
    data = raw.get("data", raw)
    return {
        "email": data.get("email"),
        "status": data.get("status") or data.get("result"),
        "score": data.get("score"),
        "disposable": data.get("disposable", False),
        "webmail": data.get("webmail", False),
        "mx_records": data.get("mx_records", True),
    }


# -- Factory -------------------------------------------------------------------

def create_people_data_server() -> PeopleDataMCPServer:
    """Build the People Data MCP server from settings.

    Raises:
        ValueError: If either ``PEOPLE_DATA_LABS_API_KEY`` or
            ``HUNTER_IO_API_KEY`` is not configured.
    """
    from aloha.config import settings

    pdl_key = settings.people_data_labs_api_key
    hunter_key = settings.hunter_io_api_key
    missing = []
    if not pdl_key:
        missing.append("PEOPLE_DATA_LABS_API_KEY")
    if not hunter_key:
        missing.append("HUNTER_IO_API_KEY")
    if missing:
        raise ValueError(
            f"{', '.join(missing)} required to use the People Data MCP server."
        )
    return PeopleDataMCPServer(pdl_api_key=pdl_key, hunter_api_key=hunter_key)
