"""UCC filing data providers — Cobalt Intelligence API + state SOS scrapers.

Provider priority for UCC data:
    1. CobaltUCCProvider — Cobalt Intelligence API (reuses existing API key)
    2. StateUCCScraper — Playwright scraper for state SOS UCC portals (FL, IL, OH)

The server orchestrates the cascade: try Cobalt first, fall back to scraper.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

log = structlog.get_logger().bind(component="ucc_providers")

_COBALT_BASE_URL = "https://api.cobaltintelligence.com/v1"
_TIMEOUT = 30.0


class CobaltUCCProvider:
    """UCC search via Cobalt Intelligence API.

    Reuses the same API key as the SOS server. If Cobalt doesn't support
    UCC queries, the server falls back to scraper-only mode.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

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

    async def search(
        self,
        debtor_name: str,
        state: str,
        filing_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search UCC filings by debtor name and state."""
        client = await self._get_client()
        params: dict[str, Any] = {
            "debtor_name": debtor_name,
            "state": state.upper(),
        }
        if filing_type:
            params["filing_type"] = filing_type

        log.debug("cobalt_ucc_search", params=params)
        response = await client.get("/ucc/search", params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("filings", data.get("results", []))

    async def get_detail(
        self,
        filing_number: str,
        state: str,
    ) -> dict[str, Any] | None:
        """Fetch full UCC filing detail by filing number and state."""
        client = await self._get_client()
        log.debug("cobalt_ucc_detail", filing_number=filing_number, state=state)
        response = await client.get(
            f"/ucc/{filing_number}",
            params={"state": state.upper()},
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


class StateUCCScraper:
    """Fallback UCC search via state SOS web portals.

    Uses Playwright to navigate state SOS UCC search pages and extract
    filing records. FL, IL, and OH have well-structured public search pages.

    NOTE: Full Playwright scraping is a future enhancement. Currently returns
    empty results with a log message.
    """

    SUPPORTED_STATES: set[str] = {"FL", "IL", "OH"}

    async def search(
        self,
        debtor_name: str,
        state: str,
        filing_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search state SOS UCC portals for filing records.

        Returns list of filing dicts or empty list if state not supported.
        """
        state_upper = state.upper()
        if state_upper not in self.SUPPORTED_STATES:
            log.info(
                "state_ucc_scraper_unsupported",
                state=state_upper,
                supported=sorted(self.SUPPORTED_STATES),
            )
            return []

        # TODO: Implement Playwright scraping for FL, IL, OH UCC portals.
        log.info(
            "state_ucc_scraper_pending",
            state=state_upper,
            debtor_name=debtor_name,
            filing_type=filing_type,
        )
        return []
