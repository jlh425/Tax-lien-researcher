"""Auction platform scraper — RealAuction (realtaxdeed.com).

RealAuction powers tax-deed auctions for many Florida counties (and some others)
via county-specific subdomains under realtaxdeed.com.

URL pattern: https://{subdomain}.realtaxdeed.com/

The portal exposes a JSON endpoint for upcoming auction listings:
  GET /index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date}&myDate={date}

Field names observed in RealAuction JSON responses:
  ACCOUNTNO / ParcelID  → parcel_id
  STARTINGBID           → opening_bid
  AUCTIONDATE           → auction_date
  SITUSADDR1/2          → address
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import structlog

from aloha.scrapers.base import BaseScraper

log = structlog.get_logger().bind(scraper="realauction")

# Known county subdomain mappings for realtaxdeed.com
REALAUCTION_ENDPOINTS: dict[tuple[str, str], str] = {
    ("FL", "orange"): "orange",
    ("FL", "hillsborough"): "hillsborough",
    ("FL", "miami-dade"): "miami-dade",
    ("FL", "broward"): "broward",
    ("FL", "palm-beach"): "palmbeach",
    ("FL", "pinellas"): "pinellas",
    ("FL", "duval"): "duval",
    ("FL", "polk"): "polk",
    ("FL", "seminole"): "seminole",
    ("FL", "volusia"): "volusia",
    ("FL", "lee"): "lee",
    ("FL", "collier"): "collier",
    ("FL", "sarasota"): "sarasota",
    ("FL", "manatee"): "manatee",
    ("FL", "pasco"): "pasco",
    ("FL", "brevard"): "brevard",
    ("FL", "st-johns"): "stjohns",
    ("FL", "alachua"): "alachua",
    ("FL", "escambia"): "escambia",
    ("FL", "leon"): "leon",
}


class RealAuctionScraper(BaseScraper):
    """Scrapes upcoming tax-deed auction listings from a RealAuction county portal.

    Args:
        subdomain: The county-specific subdomain (e.g. ``"orange"``).
        state: Two-letter state abbreviation.
        county: County name in lowercase.
    """

    def __init__(self, *, subdomain: str, state: str, county: str) -> None:
        super().__init__()
        self.subdomain = subdomain
        self.state = state.upper()
        self.county = county.lower()
        self._portal_base = f"https://{subdomain}.realtaxdeed.com"

    async def scrape(self, url: str, params: dict[str, Any] | None = None) -> Any:
        resp = await self._fetch(url, params=params)
        # RealAuction sometimes returns HTML with embedded JSON; try JSON first
        ct = resp.headers.get("content-type", "")
        if "json" in ct:
            return resp.json()
        # Fall back to text for further parsing
        return resp.text

    async def discover(self, *, max_records: int = 500) -> list[dict[str, Any]]:
        """Fetch upcoming auction listings for the next 90 days.

        Returns:
            List of normalised record dicts.
        """
        records: list[dict[str, Any]] = []
        today = date.today()

        # Fetch auctions for each of the next 90 days (RealAuction is date-specific)
        # In practice most counties hold auctions weekly or monthly; we batch by week
        for weeks_ahead in range(13):  # ~90 days / 7
            auction_date = today + timedelta(weeks=weeks_ahead)
            date_str = auction_date.strftime("%m/%d/%Y")

            url = f"{self._portal_base}/index.cfm"
            params: dict[str, Any] = {
                "zaction": "AUCTION",
                "Zmethod": "PREVIEW",
                "AUCTIONDATE": date_str,
                "myDate": date_str,
            }

            try:
                raw_data = await self.scrape(url, params=params)
            except Exception as exc:
                self.log.debug("realauction_fetch_skip", date=date_str, error=str(exc))
                continue

            items = self._parse_response(raw_data, auction_date)
            for raw in items:
                normalised = self._normalise_realauction(raw, auction_date)
                if normalised:
                    records.append(normalised)

            if len(records) >= max_records:
                break

        self.log.info(
            "realauction_discovered", state=self.state, county=self.county, count=len(records)
        )
        return records[:max_records]

    def _parse_response(self, data: Any, auction_date: date) -> list[dict[str, Any]]:
        """Extract auction item dicts from JSON or HTML response."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return (
                data.get("AUCTIONS")
                or data.get("auctions")
                or data.get("results")
                or data.get("data")
                or []
            )
        if isinstance(data, str):
            # Try to extract JSON array from HTML
            import re

            match = re.search(r"(\[\s*\{.*?\}\s*\])", data, re.DOTALL)
            if match:
                import json

                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
        return []

    def _normalise_realauction(
        self,
        raw: dict[str, Any],
        auction_date: date,
    ) -> dict[str, Any] | None:
        """Map RealAuction JSON fields to canonical scraper output."""
        parcel_id = (
            raw.get("ACCOUNTNO")
            or raw.get("ParcelID")
            or raw.get("parcel_id")
            or raw.get("PARCELID")
            or raw.get("FOLIO")
        )
        if not parcel_id:
            return None

        parcel_id = str(parcel_id).upper().strip()

        # Address
        addr1 = str(
            raw.get("SITUSADDR1") or raw.get("address1") or raw.get("ADDRESS1") or ""
        ).strip()
        addr2 = str(raw.get("SITUSADDR2") or raw.get("address2") or "").strip()
        address = f"{addr1} {addr2}".strip() or None

        opening_bid = _to_float(
            raw.get("STARTINGBID")
            or raw.get("startingBid")
            or raw.get("OPENINGBID")
            or raw.get("opening_bid")
        )

        auction_date_str = (
            _parse_date(raw.get("AUCTIONDATE") or raw.get("auctionDate"))
            or auction_date.isoformat()
        )

        portal_id = raw.get("AUCTIONID") or raw.get("id") or ""
        auction_url = (
            f"{self._portal_base}/index.cfm?zaction=AUCTION&zmethod=DETAILS&AID={portal_id}"
            if portal_id
            else None
        )

        return {
            "parcel_id": parcel_id,
            "state": self.state,
            "county": self.county,
            "address": address,
            "auction_date": auction_date_str,
            "opening_bid": opening_bid,
            "auction_platform": "realauction",
            "auction_url": auction_url,
            "instrument_type": "tax_deed",
            "source_url": self._portal_base,
        }


def _parse_date(value: Any) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    from datetime import date as _date

    try:
        _date.fromisoformat(s[:10])
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


def get_realauction_scraper(state: str, county: str) -> RealAuctionScraper | None:
    """Return a RealAuctionScraper if the county is in REALAUCTION_ENDPOINTS."""
    subdomain = REALAUCTION_ENDPOINTS.get((state.upper(), county.lower()))
    if not subdomain:
        return None
    return RealAuctionScraper(subdomain=subdomain, state=state, county=county)
