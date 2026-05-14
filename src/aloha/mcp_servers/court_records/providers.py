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
        data: dict[str, Any] = response.json()
        results: list[dict[str, Any]] = data.get("results", [])
        return results

    async def get_detail(self, docket_id: int | str) -> dict[str, Any] | None:
        """Fetch full docket detail by ID.

        Uses ``/api/rest/v4/dockets/{id}/``.
        """
        client = await self._get_client()
        log.debug("courtlistener_detail", docket_id=docket_id)
        response = await client.get(f"/api/rest/v4/dockets/{docket_id}/")
        response.raise_for_status()
        detail: dict[str, Any] = response.json()
        return detail

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


class StateLienScraper:
    """State lien search via Playwright scraping (FL, TX initially).

    Fallback provider for states with public lien portals. Uses Playwright
    to navigate state comptroller/clerk web UIs and extract lien records.

    Portals:
        FL — Florida Dept of Revenue tax warrant search
        TX — Texas Comptroller franchise tax warrant search
    """

    SUPPORTED_STATES: set[str] = {"FL", "TX"}

    _PORTALS: dict[str, dict[str, str]] = {
        "FL": {
            "url": "https://floridarevenue.com/taxes/compliance/Pages/warrantsearch.aspx",
            "domain": "floridarevenue.com",
        },
        "TX": {
            "url": "https://comptroller.texas.gov/taxes/warrant-status/",
            "domain": "comptroller.texas.gov",
        },
    }

    def __init__(self) -> None:
        from aloha.scrapers.rate_limiter import TokenBucketRateLimiter
        from aloha.scrapers.stealth.helper import StealthHelper

        self._stealth = StealthHelper()
        self._limiter = TokenBucketRateLimiter(rate=1.0, burst=3)

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

        portal = self._PORTALS[state_upper]
        await self._limiter.acquire(portal["domain"])

        try:
            if state_upper == "FL":
                return await self._scrape_fl(debtor_name, lien_type)
            elif state_upper == "TX":
                return await self._scrape_tx(debtor_name, lien_type)
        except Exception as exc:
            log.warning(
                "state_lien_scraper_failed",
                state=state_upper,
                error=str(exc),
            )
        return []

    async def _scrape_fl(self, debtor_name: str, lien_type: str | None) -> list[dict[str, Any]]:
        """Scrape Florida Dept of Revenue tax warrant search."""
        from playwright.async_api import async_playwright

        portal = self._PORTALS["FL"]
        results: list[dict[str, Any]] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await self._stealth.new_context(browser)
                page = await context.new_page()
                await page.goto(portal["url"], wait_until="networkidle", timeout=30_000)
                await self._stealth.human_delay()

                # Fill debtor name field — try multiple selectors
                for selector in [
                    'input[name*="Name"]',
                    'input[id*="Name"]',
                    'input[id*="txtSearch"]',
                    'input[type="text"]',
                ]:
                    try:
                        await page.fill(selector, debtor_name, timeout=2000)
                        break
                    except Exception:
                        continue

                await self._stealth.human_delay()

                # Submit search
                for btn in [
                    'input[type="submit"]',
                    'button[type="submit"]',
                    'input[value*="Search"]',
                    "#btnSearch",
                    'a[id*="Search"]',
                ]:
                    try:
                        await page.click(btn, timeout=2000)
                        break
                    except Exception:
                        continue

                await page.wait_for_load_state("networkidle", timeout=15_000)

                # Parse result table
                rows = await page.query_selector_all(
                    "table.results tr, table[id*='grid'] tr, #GridView1 tr, .rgMasterTable tr"
                )
                for row in rows[1:]:  # skip header
                    cells = await row.query_selector_all("td")
                    if len(cells) >= 4:
                        texts = [(await c.inner_text()).strip() for c in cells]
                        record: dict[str, Any] = {
                            "debtor": texts[0] if texts[0] else None,
                            "filing_number": texts[1] if len(texts) > 1 else None,
                            "amount": self._parse_amount(texts[2] if len(texts) > 2 else ""),
                            "filing_date": texts[3] if len(texts) > 3 else None,
                            "lien_type": lien_type or "tax",
                            "state": "FL",
                            "creditor": "FL Dept of Revenue",
                        }
                        results.append(record)

                log.info(
                    "state_lien_scraper_fl_done",
                    results=len(results),
                    debtor_name=debtor_name,
                )
            finally:
                await browser.close()

        return results

    async def _scrape_tx(self, debtor_name: str, lien_type: str | None) -> list[dict[str, Any]]:
        """Scrape Texas Comptroller tax warrant search."""
        from playwright.async_api import async_playwright

        portal = self._PORTALS["TX"]
        results: list[dict[str, Any]] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await self._stealth.new_context(browser)
                page = await context.new_page()
                await page.goto(portal["url"], wait_until="networkidle", timeout=30_000)
                await self._stealth.human_delay()

                # Fill debtor name field
                for selector in [
                    'input[name*="taxpayer"]',
                    'input[id*="taxpayer"]',
                    'input[name*="name"]',
                    'input[id*="name"]',
                    'input[type="text"]',
                ]:
                    try:
                        await page.fill(selector, debtor_name, timeout=2000)
                        break
                    except Exception:
                        continue

                await self._stealth.human_delay()

                # Submit
                for btn in [
                    'input[type="submit"]',
                    'button[type="submit"]',
                    'input[value*="Search"]',
                    "#btnSearch",
                ]:
                    try:
                        await page.click(btn, timeout=2000)
                        break
                    except Exception:
                        continue

                await page.wait_for_load_state("networkidle", timeout=15_000)

                # Parse results
                rows = await page.query_selector_all("table tr, .search-results tr, #results tr")
                for row in rows[1:]:
                    cells = await row.query_selector_all("td")
                    if len(cells) >= 3:
                        texts = [(await c.inner_text()).strip() for c in cells]
                        record: dict[str, Any] = {
                            "debtor": texts[0] if texts[0] else None,
                            "filing_number": texts[1] if len(texts) > 1 else None,
                            "amount": self._parse_amount(texts[2] if len(texts) > 2 else ""),
                            "filing_date": texts[3] if len(texts) > 3 else None,
                            "lien_type": lien_type or "tax",
                            "state": "TX",
                            "creditor": "TX Comptroller",
                        }
                        results.append(record)

                log.info(
                    "state_lien_scraper_tx_done",
                    results=len(results),
                    debtor_name=debtor_name,
                )
            finally:
                await browser.close()

        return results

    @staticmethod
    def _parse_amount(text: str) -> float | None:
        """Parse currency string like '$12,345.67' to float."""
        import re

        cleaned = re.sub(r"[^\d.]", "", text)
        if cleaned:
            try:
                return float(cleaned)
            except ValueError:
                pass
        return None
