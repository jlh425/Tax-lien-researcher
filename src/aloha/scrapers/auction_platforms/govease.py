"""Auction platform scraper — GovEase.

GovEase hosts tax lien and tax deed auctions primarily for Colorado, Iowa,
Illinois, and New Jersey counties via a JavaScript-rendered SPA at
https://app.govease.com.

Strategy:
1. Try an undocumented JSON API endpoint first (fast).
2. Fall back to Playwright if the API returns nothing (slower, more reliable).
"""

from __future__ import annotations

from typing import Any

import structlog

from aloha.scrapers.base import BaseScraper
from aloha.scrapers.stealth.helper import StealthHelper

log = structlog.get_logger().bind(scraper="govease")

_APP_BASE = "https://app.govease.com"
_API_BASE = f"{_APP_BASE}/api/v1"

# Counties known to use GovEase — expand as more are confirmed
GOVEASE_ENDPOINTS: dict[tuple[str, str], bool] = {
    ("CO", "denver"): True,
    ("CO", "el-paso"): True,
    ("CO", "arapahoe"): True,
    ("CO", "jefferson"): True,
    ("CO", "adams"): True,
    ("IA", "polk"): True,
    ("IA", "linn"): True,
    ("IA", "scott"): True,
    ("IL", "cook"): True,
    ("IL", "dupage"): True,
    ("NJ", "hudson"): True,
    ("NJ", "essex"): True,
}


class GovEaseScraper(BaseScraper):
    """Scrapes auction listings from GovEase for a given state/county.

    Args:
        state: Two-letter state abbreviation.
        county: County name in lowercase.
    """

    def __init__(self, *, state: str, county: str) -> None:
        super().__init__()
        self.state = state.upper()
        self.county = county.lower()
        self._stealth_helper = StealthHelper()

    async def scrape(self, url: str, params: dict[str, Any] | None = None) -> Any:
        resp = await self._fetch(url, params=params)
        ct = resp.headers.get("content-type", "")
        if "json" in ct:
            return resp.json()
        return resp.text

    async def discover(self, *, max_records: int = 500) -> list[dict[str, Any]]:
        """Fetch active auction listings from GovEase.

        Tries JSON API first, falls back to Playwright SPA scraping.

        Returns:
            List of normalised record dicts.
        """
        # Attempt 1: undocumented JSON API
        records = await self._try_api(max_records)
        if records:
            return records

        # Attempt 2: Playwright SPA
        return await self._playwright_scrape(max_records)

    async def _try_api(self, max_records: int) -> list[dict[str, Any]]:
        """Try the GovEase JSON API endpoint."""
        url = f"{_API_BASE}/listings"
        params = {"state": self.state, "county": self.county, "limit": min(max_records, 200)}
        try:
            data = await self.scrape(url, params=params)
        except Exception as exc:
            self.log.debug("govease_api_skip", error=str(exc))
            return []

        if not isinstance(data, (list, dict)):
            return []

        items: list[dict[str, Any]] = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("listings") or data.get("results") or data.get("data") or []

        if not items:
            return []

        results = []
        for raw in items[:max_records]:
            normalised = self._normalise_govease(raw)
            if normalised:
                results.append(normalised)

        self.log.info("govease_api_discovered", state=self.state, county=self.county, count=len(results))
        return results

    async def _playwright_scrape(self, max_records: int) -> list[dict[str, Any]]:
        """Fall back to Playwright for the JS-rendered GovEase SPA."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            self.log.warning("playwright_not_installed")
            return []

        url = f"{_APP_BASE}/auctions?state={self.state}&county={self.county}"
        records: list[dict[str, Any]] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await self._stealth_helper.new_context(browser)
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="networkidle", timeout=30_000)
                await self._stealth_helper.human_delay()

                # GovEase auction cards — try multiple selector patterns
                card_selectors = [
                    '[data-testid="auction-card"]',
                    '.auction-listing',
                    '.auction-card',
                    '[class*="AuctionCard"]',
                    '[class*="listing-item"]',
                    'article',
                ]
                raw_items: list[dict[str, str]] = []
                for selector in card_selectors:
                    try:
                        raw_items = await page.evaluate(
                            f"""() => {{
                                const cards = document.querySelectorAll({selector!r});
                                return [...cards].slice(0, 200).map(card => {{
                                    return {{ text: card.innerText.trim() }};
                                }});
                            }}"""
                        )
                        if raw_items:
                            break
                    except Exception:
                        continue

                for item in raw_items[:max_records]:
                    normalised = self._normalise_govease_text(item.get("text", ""))
                    if normalised:
                        records.append(normalised)

            except Exception as exc:
                self.log.warning("govease_playwright_failed", error=str(exc))
            finally:
                await browser.close()

        self.log.info("govease_playwright_discovered", state=self.state, county=self.county, count=len(records))
        return records

    def _normalise_govease(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        """Map a GovEase JSON listing to canonical scraper output fields."""
        parcel_id = (
            raw.get("parcel_id")
            or raw.get("parcelId")
            or raw.get("parcel_number")
            or raw.get("account_number")
            or raw.get("id")
        )
        if not parcel_id:
            return None

        parcel_id = str(parcel_id).upper().strip()

        auction_date_raw = (
            raw.get("auction_date")
            or raw.get("auctionDate")
            or raw.get("sale_date")
            or raw.get("end_date")
        )
        auction_date = _parse_date(auction_date_raw)

        opening_bid = _to_float(
            raw.get("opening_bid")
            or raw.get("openingBid")
            or raw.get("starting_bid")
            or raw.get("minimum_bid")
        )

        instrument = raw.get("sale_type") or raw.get("instrument_type") or "lien_certificate"
        if "deed" in str(instrument).lower():
            instrument = "tax_deed"
        else:
            instrument = "lien_certificate"

        return {
            "parcel_id": parcel_id,
            "state": self.state,
            "county": self.county,
            "address": str(raw.get("address") or raw.get("property_address") or "").strip() or None,
            "auction_date": auction_date,
            "opening_bid": opening_bid,
            "auction_platform": "govease",
            "auction_url": raw.get("url") or raw.get("auction_url") or f"{_APP_BASE}/auctions",
            "instrument_type": instrument,
            "source_url": _APP_BASE,
        }

    def _normalise_govease_text(self, text: str) -> dict[str, Any] | None:
        """Parse a GovEase auction card's inner text into canonical fields."""
        import re
        if not text:
            return None

        # Look for APN-like string: digits/dashes 6-20 chars
        apn_match = re.search(r'\b([\dA-Z][\dA-Z\-\.\/]{5,19})\b', text, re.IGNORECASE)
        if not apn_match:
            return None

        parcel_id = apn_match.group(1).upper().strip()

        # Look for dollar amount (opening bid)
        bid_match = re.search(r'\$[\d,]+(?:\.\d{2})?', text)
        opening_bid = _to_float(bid_match.group(0)) if bid_match else None

        # Look for a date
        date_match = re.search(r'\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}', text)
        auction_date = _parse_date(date_match.group(0)) if date_match else None

        return {
            "parcel_id": parcel_id,
            "state": self.state,
            "county": self.county,
            "address": None,
            "auction_date": auction_date,
            "opening_bid": opening_bid,
            "auction_platform": "govease",
            "auction_url": f"{_APP_BASE}/auctions",
            "instrument_type": "lien_certificate",
            "source_url": _APP_BASE,
        }


def _parse_date(value: Any) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    from datetime import date
    try:
        date.fromisoformat(s[:10])
        return s[:10]
    except ValueError:
        pass
    try:
        parts = s.split("/")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
    except Exception:
        pass
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def get_govease_scraper(state: str, county: str) -> GovEaseScraper | None:
    """Return a GovEaseScraper if the county is in GOVEASE_ENDPOINTS."""
    if (state.upper(), county.lower()) not in GOVEASE_ENDPOINTS:
        return None
    return GovEaseScraper(state=state, county=county)
