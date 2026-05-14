"""Tier 2 — qPublic (Schneider Geospatial) assessor portal scraper.

qPublic.net is used by 300+ counties, primarily in the southeastern US.
URL pattern: https://qpublic.schneidercorp.com/Application.aspx?AppID=...&LayerID=...
Or county-specific: https://[county].qpublic.net/...

The API endpoint pattern (most qPublic deployments expose this):
  GET /qpublic_county/search?dev_id=PARCEL&dev=PARCEL_NUM
  GET /qpublic_county/parcels/{parcel_id}  → JSON

Many counties also have a REST-like API:
  GET /qpublic_county/api/search?parcel_id=...

This scraper tries the JSON API first (faster), then falls back to Playwright
HTML parsing if the API is gated.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from aloha.scrapers.stealth.helper import StealthHelper as _StealthHelperCls

_stealth = _StealthHelperCls()
log = structlog.get_logger().bind(scraper="qpublic")

# Well-known qPublic API patterns
_API_PATTERNS = [
    "{base}/api/parcels/{apn}",
    "{base}/api/search?parcel_id={apn}",
    "{base}/search?dev_id=PARCEL&dev={apn}",
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/html, */*",
}


class QPublicScraper:
    """Scraper for qPublic / Schneider Geospatial county assessor portals.

    Attempts JSON API first (fast), falls back to Playwright (slow).
    """

    def __init__(self, base_url: str, county_code: str) -> None:
        """
        Args:
            base_url: Root URL of the qPublic portal.
                      Example: ``"https://qpublic.schneidercorp.com"``
            county_code: The county-specific path segment.
                         Example: ``"GA_DeKalb"``
        """
        self.base_url = base_url.rstrip("/")
        self.county_code = county_code
        self.log = log.bind(county_code=county_code)

    async def query_by_apn(self, apn: str) -> dict[str, Any] | None:
        """Search for a parcel by APN."""
        apn_clean = re.sub(r"[\s\-]", "", apn).upper()

        # Try JSON API endpoint
        result = await self._try_api(apn_clean)
        if result:
            return result

        # Fall back to Playwright HTML scraping
        return await self._playwright_scrape(apn_clean)

    async def _try_api(self, apn: str) -> dict[str, Any] | None:
        """Attempt to fetch parcel data from the qPublic JSON API."""
        county_base = f"{self.base_url}/{self.county_code}"

        async with httpx.AsyncClient(headers=_HEADERS, timeout=15.0) as client:
            for pattern in _API_PATTERNS:
                url = pattern.format(base=county_base, apn=apn)
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        ct = response.headers.get("content-type", "")
                        if "json" in ct:
                            data = response.json()
                            return _normalise_qpublic_api(data, source_url=url)
                except Exception:
                    continue

        return None

    async def _playwright_scrape(self, apn: str) -> dict[str, Any] | None:
        """Fall back to Playwright HTML scraping for gated qPublic portals."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            self.log.warning("playwright_not_installed")
            return None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await _stealth.new_context(browser)
            page = await context.new_page()
            try:
                search_url = f"{self.base_url}/{self.county_code}/search"
                await page.goto(search_url, wait_until="networkidle", timeout=30_000)

                # qPublic search form typically has a "parcel" input
                for selector in [
                    'input[name*="parcel"]',
                    'input[id*="parcel"]',
                    'input[name*="Parcel"]',
                    'input[placeholder*="parcel" i]',
                ]:
                    try:
                        await page.fill(selector, apn, timeout=2000)
                        await _stealth.human_delay()
                        break
                    except Exception:
                        continue

                # Submit
                try:
                    await page.keyboard.press("Enter")
                    await page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception as e:
                    log.warning("qpublic_submit_failed", apn=apn, error=str(e))

                # Parse detail page
                raw = await _parse_qpublic_html(page)
                if raw:
                    return _normalise_qpublic_html(raw, source_url=page.url)

            except Exception as exc:
                self.log.warning("qpublic_playwright_failed", apn=apn, error=str(exc))
            finally:
                await browser.close()

        return None


async def _parse_qpublic_html(page: Any) -> dict[str, str]:
    """Extract label/value pairs from a qPublic detail page."""
    raw: dict[str, str] = {}
    rows = await page.query_selector_all("table tr, dl dt, .field-label")
    for row in rows:
        cells = await row.query_selector_all("td, dd")
        if len(cells) >= 2:
            label = (await cells[0].inner_text()).strip().rstrip(":")
            value = (await cells[1].inner_text()).strip()
            if label and value:
                raw[label.upper()] = value
    return raw


def _normalise_qpublic_api(data: dict[str, Any], source_url: str = "") -> dict[str, Any] | None:
    """Map a qPublic JSON API response to canonical parcel fields."""
    if not data:
        return None
    # qPublic API varies by county; try common field names
    def pick(*keys: str) -> Any:
        for k in keys:
            v = data.get(k) or data.get(k.lower()) or data.get(k.upper())
            if v is not None:
                return v
        return None

    parcel_id = pick("parcelId", "parcel_id", "ParcelID", "APN", "apn")
    if not parcel_id:
        return None

    return {
        "parcel_id": str(parcel_id),
        "address": pick("propertyAddress", "situs_address", "PropertyAddress"),
        "owner_of_record": pick("ownerName", "owner_name", "OwnerName"),
        "assessed_total": _to_int(pick("totalValue", "assessedValue", "TotalValue")),
        "acreage": _to_float(pick("landArea", "acreage", "Acreage")),
        "zoning": pick("zoning", "Zoning"),
        "land_use_code": pick("landUse", "land_use", "UseCode"),
        "year_built": _to_int(pick("yearBuilt", "year_built", "YearBuilt")),
        "legal_description": pick("legalDescription", "legal_desc", "LegalDescription"),
        "source_url": source_url,
        "raw_attributes": data,
    }


def _normalise_qpublic_html(raw: dict[str, str], source_url: str = "") -> dict[str, Any]:
    """Map scraped HTML label/value pairs to canonical parcel fields."""
    def pick(*keys: str) -> str | None:
        for k in keys:
            v = raw.get(k.upper())
            if v:
                return v
        return None

    return {
        "address": pick("Property Address", "Situs Address", "Location"),
        "owner_of_record": pick("Owner", "Owner Name", "Property Owner"),
        "assessed_total": _to_int(pick("Total Value", "Total Assessed", "Appraised Value")),
        "acreage": _to_float(pick("Land Area", "Acreage", "Lot Size")),
        "zoning": pick("Zoning", "Zone Code"),
        "land_use_code": pick("Land Use", "Use Code"),
        "year_built": _to_int(pick("Year Built", "Yr Built")),
        "legal_description": pick("Legal Description", "Legal Desc"),
        "source_url": source_url,
        "raw_attributes": raw,
    }


def _to_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(float(re.sub(r"[^\d.]", "", str(val))))
    except (ValueError, TypeError):
        return None


def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(re.sub(r"[^\d.]", "", str(val)))
    except (ValueError, TypeError):
        return None


# ── County endpoint registry ──────────────────────────────────────────────────

QPUBLIC_ENDPOINTS: dict[tuple[str, str], dict[str, str]] = {
    # Georgia
    ("GA", "dekalb"): {"base_url": "https://qpublic.schneidercorp.com", "county_code": "GA_DeKalb"},
    ("GA", "cobb"): {"base_url": "https://qpublic.schneidercorp.com", "county_code": "GA_Cobb"},
    ("GA", "henry"): {"base_url": "https://qpublic.schneidercorp.com", "county_code": "GA_Henry"},
    ("GA", "paulding"): {"base_url": "https://qpublic.schneidercorp.com", "county_code": "GA_Paulding"},
    # Florida
    ("FL", "alachua"): {"base_url": "https://qpublic.schneidercorp.com", "county_code": "FL_Alachua"},
    ("FL", "clay"): {"base_url": "https://qpublic.schneidercorp.com", "county_code": "FL_Clay"},
    ("FL", "nassau"): {"base_url": "https://qpublic.schneidercorp.com", "county_code": "FL_Nassau"},
    # Louisiana
    ("LA", "east baton rouge"): {"base_url": "https://qpublic.schneidercorp.com", "county_code": "LA_EastBatonRouge"},
    ("LA", "jefferson"): {"base_url": "https://qpublic.schneidercorp.com", "county_code": "LA_Jefferson"},
}


def get_qpublic_scraper(state: str, county: str) -> QPublicScraper | None:
    """Return a configured scraper if this county uses qPublic."""
    entry = QPUBLIC_ENDPOINTS.get((state.upper(), county.lower()))
    if not entry:
        return None
    return QPublicScraper(base_url=entry["base_url"], county_code=entry["county_code"])
