"""Court records data providers — CourtListener API + state lien scrapers.

Provider priority for court/lien data:
    1. CourtListenerProvider — free REST API v4 (RECAP dockets, opinions)
    2. StateLienScraper — Playwright scraper for state lien portals (FL, TX)

Each provider is used directly by the server; no ProviderChain needed because
the server orchestrates the cascade per-tool (federal vs state logic differs).
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

log = structlog.get_logger().bind(component="court_records_providers")

_COURTLISTENER_BASE_URL = "https://www.courtlistener.com"
_TIMEOUT = 30.0


class CourtListenerProvider:
    """Federal case search via CourtListener REST API v4.

    API docs: https://www.courtlistener.com/help/api/rest/
    Auth: ``Authorization: Token <api_key>`` header.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=_COURTLISTENER_BASE_URL,
                headers={
                    "Authorization": f"Token {self._api_key}",
                    "Accept": "application/json",
                },
                timeout=httpx.Timeout(_TIMEOUT),
            )
        return self._client

    async def search(
        self,
        party_name: str,
        state: str | None = None,
        case_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search RECAP dockets by party name.

        Uses ``/api/rest/v4/search/?type=r`` (RECAP type).
        """
        client = await self._get_client()
        params: dict[str, Any] = {
            "q": party_name,
            "type": "r",  # RECAP dockets
        }
        if state:
            # CourtListener court filter uses state abbreviation codes
            params["court"] = state.lower()
        if case_type:
            params["case_name"] = case_type  # best-effort filter

        log.debug("courtlistener_search", params=params)
        response = await client.get("/api/rest/v4/search/", params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    async def get_detail(self, docket_id: int | str) -> dict[str, Any] | None:
        """Fetch full docket detail by ID.

        Uses ``/api/rest/v4/dockets/{id}/``.
        """
        client = await self._get_client()
        log.debug("courtlistener_detail", docket_id=docket_id)
        response = await client.get(f"/api/rest/v4/dockets/{docket_id}/")
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


class StateLienScraper:
    """State lien search via Playwright scraping (FL, TX initially).

    Fallback provider for states with public lien portals. Uses Playwright
    to navigate state court/clerk web UIs and extract lien records.

    NOTE: Full Playwright scraping is a future enhancement. Currently returns
    empty results with a log message indicating the state is not yet supported
    or that scraping is pending implementation.
    """

    SUPPORTED_STATES: set[str] = {"FL", "TX"}

    async def search(
        self,
        debtor_name: str,
        state: str,
        lien_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search state lien portals for lien records.

        Returns list of lien dicts or empty list if state not supported.
        """
        state_upper = state.upper()
        if state_upper not in self.SUPPORTED_STATES:
            log.info(
                "state_lien_scraper_unsupported",
                state=state_upper,
                supported=sorted(self.SUPPORTED_STATES),
            )
            return []

        # TODO: Implement Playwright scraping for FL and TX lien portals.
        # For now, log and return empty — the server will surface this
        # gracefully to the agent.
        log.info(
            "state_lien_scraper_pending",
            state=state_upper,
            debtor_name=debtor_name,
            lien_type=lien_type,
        )
        return []
