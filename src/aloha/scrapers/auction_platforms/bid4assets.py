"""Auction platform scraper — Bid4Assets.

Bid4Assets hosts tax deed auctions for counties across multiple states.
Their public search API returns JSON listings filterable by category and state.

API endpoint (best-guess; field names should be validated against live API):
  GET https://www.bid4assets.com/api/auctions?category=tax-deed&state={state}

Note: Bid4Assets does not publish a formal API spec. The field mapping in
``_normalise_b4a`` is based on observed response structures and may need
adjustment if the API changes.
"""

from __future__ import annotations

from typing import Any

import structlog

from aloha.scrapers.base import BaseScraper

log = structlog.get_logger().bind(scraper="bid4assets")

_BASE_URL = "https://www.bid4assets.com"
_AUCTION_API = f"{_BASE_URL}/api/auctions"


class Bid4AssetsScraper(BaseScraper):
    """Scrapes active tax-deed auction listings from Bid4Assets.

    Args:
        state: Two-letter state abbreviation (e.g. ``"FL"``).
        county: County name in lowercase (e.g. ``"orange"``).
    """

    def __init__(self, *, state: str, county: str | None = None) -> None:
        super().__init__()
        self.state = state.upper()
        self.county = county.lower() if county else None

    async def scrape(self, url: str, params: dict[str, Any] | None = None) -> Any:
        resp = await self._fetch(url, params=params)
        return resp.json()

    async def discover(self, *, max_records: int = 500) -> list[dict[str, Any]]:
        """Fetch active tax-deed auction listings for this state/county.

        Returns:
            List of normalised record dicts.
        """
        records: list[dict[str, Any]] = []
        page = 1
        per_page = 100

        while len(records) < max_records:
            params: dict[str, Any] = {
                "category": "tax-deed",
                "state": self.state,
                "page": page,
                "per_page": per_page,
            }
            if self.county:
                params["county"] = self.county

            try:
                data = await self.scrape(_AUCTION_API, params=params)
            except Exception as exc:
                self.log.warning("bid4assets_fetch_failed", page=page, error=str(exc))
                break

            # Support both {"auctions": [...]} and raw list responses
            if isinstance(data, dict):
                items = data.get("auctions") or data.get("results") or data.get("data") or []
            elif isinstance(data, list):
                items = data
            else:
                items = []

            if not items:
                break

            for raw in items:
                normalised = self._normalise_b4a(raw)
                if normalised:
                    records.append(normalised)

            if len(items) < per_page:
                break  # Last page
            page += 1

        self.log.info("bid4assets_discovered", state=self.state, count=len(records))
        return records[:max_records]

    def _normalise_b4a(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        """Map a Bid4Assets auction record to canonical scraper output fields."""
        # Try common field name variants for parcel ID
        parcel_id = (
            raw.get("parcel_id")
            or raw.get("parcelId")
            or raw.get("parcel_number")
            or raw.get("apn")
            or raw.get("account_number")
            or raw.get("folio")
        )
        if not parcel_id:
            return None

        parcel_id = str(parcel_id).upper().strip()

        # County from record or constructor
        county = str(raw.get("county") or raw.get("location") or self.county or "").lower().strip()

        # Auction date
        auction_date_raw = (
            raw.get("auction_date")
            or raw.get("auctionDate")
            or raw.get("end_date")
            or raw.get("close_date")
        )
        auction_date = _parse_date_str(auction_date_raw)

        # Opening bid
        opening_bid = _to_float(
            raw.get("starting_bid")
            or raw.get("startingBid")
            or raw.get("opening_bid")
            or raw.get("minimum_bid")
        )

        # Auction URL
        auction_url = raw.get("url") or raw.get("auction_url") or raw.get("link")
        if auction_url and not auction_url.startswith("http"):
            auction_url = f"{_BASE_URL}{auction_url}"

        return {
            "parcel_id": parcel_id,
            "state": self.state,
            "county": county or self.county or "",
            "address": str(raw.get("address") or raw.get("property_address") or "").strip()
            or None,
            "auction_date": auction_date,
            "opening_bid": opening_bid,
            "auction_platform": "bid4assets",
            "auction_url": auction_url,
            "instrument_type": "tax_deed",
            "source_url": _AUCTION_API,
        }


def _parse_date_str(value: Any) -> str | None:
    """Return ISO date string or None."""
    if not value:
        return None
    from datetime import date

    s = str(value).strip()
    # Try YYYY-MM-DD
    try:
        date.fromisoformat(s[:10])
        return s[:10]
    except ValueError:
        pass
    # Try MM/DD/YYYY
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


def get_bid4assets_scraper(state: str, county: str | None = None) -> Bid4AssetsScraper:
    """Factory: return a Bid4AssetsScraper for the given state/county."""
    return Bid4AssetsScraper(state=state, county=county)
