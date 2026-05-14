"""Tier 2 — Tyler Technologies (iasWorld / EagleWeb) assessor portal scraper.

Tyler Technologies powers county assessor portals across hundreds of US counties
under product names: iasWorld, EagleWeb, INCODE, NeoGov, SalesPoint.

The most common public-facing variant is EagleWeb (also branded "Tyler MUNIS" in
some counties). Their portals share a recognizable URL and HTML structure:
  - /EagleWeb/accounts/search/SearchForm.aspx
  - /EagleWeb/accounts/Profile.aspx?AccountNumber=...
  - /AIRS/InquiryScreen.aspx

This scraper handles the most common EagleWeb search + detail flow using
Playwright for JS-rendered content.

Counties using Tyler EagleWeb (partial list):
- GA: Fulton, Gwinnett, DeKalb, Cherokee, Forsyth, Hall, Bartow
- TX: Collin, Tarrant (some sites), Henderson
- SC: Greenville, Richland, Charleston, Lexington
- TN: Davidson, Shelby
- AZ: Yavapai, Mohave, La Paz

Usage:
    scraper = TylerEagleWebScraper(base_url="https://eagleweb.countyname.gov/EagleWeb")
    record = await scraper.query_by_apn("123-456-789")
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from aloha.scrapers.stealth.helper import StealthHelper as _StealthHelperCls

_stealth = _StealthHelperCls()
log = structlog.get_logger().bind(scraper="tyler_eagleweb")


class TylerEagleWebScraper:
    """Playwright-based scraper for Tyler EagleWeb assessor portals.

    Implements the two-step flow:
    1. POST to SearchForm.aspx with AccountNumber
    2. Parse Profile.aspx for property details

    Note: Requires ``playwright`` to be installed and browsers to be initialised
    (``playwright install chromium``).
    """

    def __init__(self, base_url: str) -> None:
        """
        Args:
            base_url: Base URL of the EagleWeb portal.
                      Example: ``"https://eagleweb.gwinnettcounty.com/EagleWeb"``
        """
        self.base_url = base_url.rstrip("/")
        self.log = log.bind(base_url=base_url)

    async def query_by_apn(self, apn: str) -> dict[str, Any] | None:
        """Search for a parcel by APN/Account Number and return parsed details.

        Args:
            apn: Assessor parcel number (with or without dashes).

        Returns:
            Normalised parcel dict, or ``None`` if not found.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            self.log.error(
                "playwright_not_installed",
                note="pip install playwright && playwright install chromium",
            )
            return None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await _stealth.new_context(browser)
            page = await context.new_page()

            try:
                # ── Step 1: Load search form ──────────────────────────────
                search_url = f"{self.base_url}/accounts/search/SearchForm.aspx"
                await page.goto(search_url, wait_until="networkidle", timeout=30_000)

                # Fill account number field (most EagleWeb portals use this name)
                for selector in [
                    'input[name*="AccountNumber"]',
                    'input[id*="AccountNumber"]',
                    'input[name*="ACCT"]',
                    'input[id*="searchAccountNumber"]',
                ]:
                    try:
                        await page.fill(selector, apn, timeout=2000)
                        await _stealth.human_delay()
                        break
                    except Exception:
                        continue

                # Submit the search
                for btn_selector in [
                    'input[type="submit"]',
                    'button[type="submit"]',
                    'input[value*="Search"]',
                    "#btnSearch",
                ]:
                    try:
                        await page.click(btn_selector, timeout=2000)
                        await _stealth.human_delay()
                        break
                    except Exception:
                        continue

                await page.wait_for_load_state("networkidle", timeout=15_000)

                # ── Step 2: Check for direct profile redirect ──────────────
                current_url = page.url
                if "Profile.aspx" in current_url or "AccountNumber=" in current_url:
                    return await self._parse_profile_page(page, current_url)

                # ── Step 3: Parse search results to find the matching row ──
                result_link = await self._find_result_link(page, apn)
                if not result_link:
                    self.log.debug("apn_not_found", apn=apn)
                    return None

                await page.goto(result_link, wait_until="networkidle", timeout=15_000)
                return await self._parse_profile_page(page, result_link)

            except Exception as exc:
                self.log.warning("eagleweb_scrape_failed", apn=apn, error=str(exc))
                return None
            finally:
                await browser.close()

    async def _find_result_link(self, page: Any, apn: str) -> str | None:
        """Locate the first matching profile link in search results."""
        # EagleWeb results are typically in a GridView table
        links = await page.query_selector_all('a[href*="Profile.aspx"]')
        if links:
            href = await links[0].get_attribute("href")
            if href:
                if href.startswith("http"):
                    return href
                return f"{self.base_url}/{href.lstrip('/')}"
        return None

    async def _parse_profile_page(self, page: Any, url: str) -> dict[str, Any]:
        """Extract property data from an EagleWeb Profile.aspx page."""
        # EagleWeb profiles render data in label/value pairs in a table
        raw: dict[str, str] = {}

        # Strategy: find all table rows with two cells (label + value)
        rows = await page.query_selector_all("table tr")
        for row in rows:
            cells = await row.query_selector_all("td, th")
            if len(cells) >= 2:
                label_text = (await cells[0].inner_text()).strip().rstrip(":")
                value_text = (await cells[1].inner_text()).strip()
                if label_text and value_text:
                    raw[label_text.upper()] = value_text

        return _normalise_eagleweb(raw, source_url=url)


# ── Normalisation ─────────────────────────────────────────────────────────────

_ASSESSED_PATTERNS = ("TOTAL ASSESSMENT", "ASSESSED VALUE", "TOTAL VALUE", "APPRAISED VALUE")
_OWNER_PATTERNS = ("OWNER", "OWNER NAME", "PROPERTY OWNER")
_ADDRESS_PATTERNS = ("PROPERTY ADDRESS", "SITUS ADDRESS", "LOCATION ADDRESS")
_ACREAGE_PATTERNS = ("LAND AREA", "ACREAGE", "LOT SIZE", "LAND SIZE")
_ZONING_PATTERNS = ("ZONING", "ZONE", "ZONING CODE")
_LAND_USE_PATTERNS = ("LAND USE", "USE CODE", "PROPERTY USE")
_YEAR_BUILT_PATTERNS = ("YEAR BUILT", "YR BUILT", "YEAR OF CONSTRUCTION")
_LEGAL_PATTERNS = ("LEGAL DESCRIPTION", "LEGAL DESC", "LEGAL")


def _pick_raw(raw: dict[str, str], patterns: tuple[str, ...]) -> str | None:
    for p in patterns:
        val = raw.get(p) or raw.get(p.title())
        if val:
            return val
    return None


def _parse_money(val: str | None) -> int | None:
    if not val:
        return None
    cleaned = re.sub(r"[^\d.]", "", val.replace(",", ""))
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


def _parse_float(val: str | None) -> float | None:
    if not val:
        return None
    cleaned = re.sub(r"[^\d.]", "", val)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _normalise_eagleweb(raw: dict[str, str], source_url: str = "") -> dict[str, Any]:
    """Map raw EagleWeb label/value pairs to our canonical parcel fields."""
    return {
        "owner_of_record": _pick_raw(raw, _OWNER_PATTERNS),
        "address": _pick_raw(raw, _ADDRESS_PATTERNS),
        "assessed_total": _parse_money(_pick_raw(raw, _ASSESSED_PATTERNS)),
        "acreage": _parse_float(_pick_raw(raw, _ACREAGE_PATTERNS)),
        "zoning": _pick_raw(raw, _ZONING_PATTERNS),
        "land_use_code": _pick_raw(raw, _LAND_USE_PATTERNS),
        "year_built": _parse_money(_pick_raw(raw, _YEAR_BUILT_PATTERNS)),
        "legal_description": _pick_raw(raw, _LEGAL_PATTERNS),
        "source_url": source_url,
        "raw_attributes": raw,
    }


# ── County endpoint registry ──────────────────────────────────────────────────
# Map (STATE, county_lower) → EagleWeb base URL

EAGLEWEB_ENDPOINTS: dict[tuple[str, str], str] = {
    # Georgia
    ("GA", "gwinnett"): "https://eagleweb.gwinnettcounty.com/EagleWeb",
    ("GA", "cherokee"): "https://eagleweb.cherokeega.com/EagleWeb",
    ("GA", "forsyth"): "https://eagleweb.forsythco.com/EagleWeb",
    ("GA", "hall"): "https://eagleweb.hallcounty.org/EagleWeb",
    # South Carolina
    ("SC", "greenville"): "https://eagleweb.greenvillecounty.org/EagleWeb",
    ("SC", "richland"): "https://eagleweb.rcgov.us/EagleWeb",
    ("SC", "lexington"): "https://eagleweb.lexingtonsc.gov/EagleWeb",
    # Tennessee
    ("TN", "davidson"): "https://eagleweb.nashville.gov/EagleWeb",
    # Arizona
    ("AZ", "yavapai"): "https://eagleweb.yavapai.us/EagleWeb",
    ("AZ", "mohave"): "https://eagleweb.mcassessor.com/EagleWeb",
}


def get_eagleweb_scraper(state: str, county: str) -> TylerEagleWebScraper | None:
    """Return a configured scraper if this county uses Tyler EagleWeb."""
    url = EAGLEWEB_ENDPOINTS.get((state.upper(), county.lower()))
    if not url:
        return None
    return TylerEagleWebScraper(base_url=url)
