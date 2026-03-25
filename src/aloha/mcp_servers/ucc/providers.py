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
    filing records.

    Portals:
        FL — Sunbiz UCC filing search (Div. of Corporations)
        IL — Illinois SOS UCC search
        OH — Ohio SOS business portal
    """

    SUPPORTED_STATES: set[str] = {"FL", "IL", "OH"}

    _PORTALS: dict[str, dict[str, str]] = {
        "FL": {
            "url": "https://efile.sunbiz.org/UCCFiling/FilingSearch",
            "domain": "efile.sunbiz.org",
        },
        "IL": {
            "url": "https://www.ilsos.gov/UCC/UCCSrch.html",
            "domain": "www.ilsos.gov",
        },
        "OH": {
            "url": "https://bsportal.ohiosos.gov/DynamicReports",
            "domain": "bsportal.ohiosos.gov",
        },
    }

    def __init__(self) -> None:
        from aloha.scrapers.stealth.helper import StealthHelper
        from aloha.scrapers.rate_limiter import TokenBucketRateLimiter

        self._stealth = StealthHelper()
        self._limiter = TokenBucketRateLimiter(rate=1.0, burst=3)

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

        portal = self._PORTALS[state_upper]
        await self._limiter.acquire(portal["domain"])

        try:
            if state_upper == "FL":
                return await self._scrape_fl(debtor_name, filing_type)
            elif state_upper == "IL":
                return await self._scrape_il(debtor_name, filing_type)
            elif state_upper == "OH":
                return await self._scrape_oh(debtor_name, filing_type)
        except Exception as exc:
            log.warning(
                "state_ucc_scraper_failed",
                state=state_upper,
                error=str(exc),
            )
        return []

    async def _scrape_fl(
        self, debtor_name: str, filing_type: str | None
    ) -> list[dict[str, Any]]:
        """Scrape Florida Sunbiz UCC filing search."""
        from playwright.async_api import async_playwright

        portal = self._PORTALS["FL"]
        results: list[dict[str, Any]] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await self._stealth.new_context(browser)
                page = await context.new_page()
                await page.goto(
                    portal["url"], wait_until="networkidle", timeout=30_000
                )
                await self._stealth.human_delay()

                # Select "Debtor Name" search type if radio/dropdown exists
                for selector in [
                    'input[value*="debtor" i]',
                    'select[name*="SearchType"]',
                    'input[id*="Debtor"]',
                ]:
                    try:
                        el = await page.query_selector(selector)
                        if el:
                            tag = await el.evaluate("e => e.tagName")
                            if tag == "INPUT":
                                await el.click()
                            elif tag == "SELECT":
                                await page.select_option(selector, label="Debtor Name")
                            break
                    except Exception:
                        continue

                await self._stealth.human_delay()

                # Fill debtor name
                for selector in [
                    'input[name*="SearchValue"]',
                    'input[name*="DebtorName"]',
                    'input[id*="SearchValue"]',
                    'input[id*="search"]',
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
                    '#btnSearch',
                ]:
                    try:
                        await page.click(btn, timeout=2000)
                        break
                    except Exception:
                        continue

                await page.wait_for_load_state("networkidle", timeout=15_000)

                # Parse result table
                rows = await page.query_selector_all(
                    "table tr, #GridView1 tr, .rgMasterTable tr, "
                    "#searchResults tr"
                )
                for row in rows[1:]:  # skip header
                    cells = await row.query_selector_all("td")
                    if len(cells) >= 3:
                        texts = [
                            (await c.inner_text()).strip() for c in cells
                        ]
                        record = self._build_filing(
                            texts, state="FL", filing_type=filing_type
                        )
                        if record:
                            results.append(record)

                log.info(
                    "state_ucc_scraper_fl_done",
                    results=len(results),
                    debtor_name=debtor_name,
                )
            finally:
                await browser.close()

        return results

    async def _scrape_il(
        self, debtor_name: str, filing_type: str | None
    ) -> list[dict[str, Any]]:
        """Scrape Illinois SOS UCC search."""
        from playwright.async_api import async_playwright

        portal = self._PORTALS["IL"]
        results: list[dict[str, Any]] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await self._stealth.new_context(browser)
                page = await context.new_page()
                await page.goto(
                    portal["url"], wait_until="networkidle", timeout=30_000
                )
                await self._stealth.human_delay()

                # IL SOS has a form with debtor name fields
                # Try organization name first, then individual name
                for selector in [
                    'input[name*="OrgName"]',
                    'input[name*="orgName"]',
                    'input[name*="debtorName"]',
                    'input[id*="OrgName"]',
                    '#txtOrgName',
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
                    'input[value*="Submit"]',
                ]:
                    try:
                        await page.click(btn, timeout=2000)
                        break
                    except Exception:
                        continue

                await page.wait_for_load_state("networkidle", timeout=15_000)

                # Parse results
                rows = await page.query_selector_all(
                    "table tr, .search-results tr, #results tr"
                )
                for row in rows[1:]:
                    cells = await row.query_selector_all("td")
                    if len(cells) >= 3:
                        texts = [
                            (await c.inner_text()).strip() for c in cells
                        ]
                        record = self._build_filing(
                            texts, state="IL", filing_type=filing_type
                        )
                        if record:
                            results.append(record)

                log.info(
                    "state_ucc_scraper_il_done",
                    results=len(results),
                    debtor_name=debtor_name,
                )
            finally:
                await browser.close()

        return results

    async def _scrape_oh(
        self, debtor_name: str, filing_type: str | None
    ) -> list[dict[str, Any]]:
        """Scrape Ohio SOS business portal UCC search."""
        from playwright.async_api import async_playwright

        portal = self._PORTALS["OH"]
        results: list[dict[str, Any]] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await self._stealth.new_context(browser)
                page = await context.new_page()
                await page.goto(
                    portal["url"], wait_until="networkidle", timeout=30_000
                )
                await self._stealth.human_delay()

                # OH portal may have UCC search tab/link
                for nav in [
                    'a[href*="UCC" i]',
                    'a:text("UCC")',
                    'a:text("Uniform Commercial Code")',
                ]:
                    try:
                        await page.click(nav, timeout=3000)
                        await page.wait_for_load_state(
                            "networkidle", timeout=10_000
                        )
                        break
                    except Exception:
                        continue

                await self._stealth.human_delay()

                # Fill search
                for selector in [
                    'input[name*="DebtorName"]',
                    'input[name*="name"]',
                    'input[id*="search"]',
                    'input[type="text"]',
                ]:
                    try:
                        await page.fill(selector, debtor_name, timeout=2000)
                        break
                    except Exception:
                        continue

                await self._stealth.human_delay()

                for btn in [
                    'input[type="submit"]',
                    'button[type="submit"]',
                    'input[value*="Search"]',
                    'button:text("Search")',
                ]:
                    try:
                        await page.click(btn, timeout=2000)
                        break
                    except Exception:
                        continue

                await page.wait_for_load_state("networkidle", timeout=15_000)

                rows = await page.query_selector_all(
                    "table tr, .results tr, #searchResults tr"
                )
                for row in rows[1:]:
                    cells = await row.query_selector_all("td")
                    if len(cells) >= 3:
                        texts = [
                            (await c.inner_text()).strip() for c in cells
                        ]
                        record = self._build_filing(
                            texts, state="OH", filing_type=filing_type
                        )
                        if record:
                            results.append(record)

                log.info(
                    "state_ucc_scraper_oh_done",
                    results=len(results),
                    debtor_name=debtor_name,
                )
            finally:
                await browser.close()

        return results

    @staticmethod
    def _build_filing(
        texts: list[str],
        state: str,
        filing_type: str | None,
    ) -> dict[str, Any] | None:
        """Build a normalised filing dict from table cell texts.

        Typical column order: filing_number, debtor_name, filing_date, ...
        but varies by state. We grab the first 5 columns and assign
        canonical keys.
        """
        if not texts or not any(texts):
            return None

        import re

        def parse_date(s: str) -> str | None:
            """Check if string looks like a date."""
            if re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", s):
                return s
            if re.search(r"\d{4}-\d{2}-\d{2}", s):
                return s
            return None

        # Heuristic: find filing number (alphanumeric with dashes) and date
        filing_number = None
        debtor_name = None
        filing_date = None
        secured_party = None

        for text in texts:
            if not text:
                continue
            if not filing_number and re.match(
                r"^[A-Z0-9]{2,}[-]?\d+", text
            ):
                filing_number = text
            elif not filing_date and parse_date(text):
                filing_date = text
            elif not debtor_name:
                debtor_name = text
            elif not secured_party:
                secured_party = text

        return {
            "filing_number": filing_number or texts[0],
            "debtor_name": debtor_name,
            "secured_party": secured_party,
            "filing_date": filing_date,
            "filing_type": filing_type,
            "state": state,
            "collateral": None,
            "lapse_date": None,
        }
