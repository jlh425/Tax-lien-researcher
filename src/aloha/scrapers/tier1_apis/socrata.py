"""Tier 1 — Socrata Open Data API scraper.

Many counties publish delinquent tax lists on Socrata (data.socrata.com,
county data portals, data.gov). This scraper queries the SODA v2.1 JSON API
directly — zero Playwright, zero HTML parsing.

Usage:
    scraper = SocrataDiscoveryScraper(state="FL", county="orange")
    records = await scraper.discover(max_records=5000)
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import structlog

from aloha.scrapers.base import BaseScraper

log = structlog.get_logger().bind(scraper="socrata")

# ── County Socrata dataset registry ───────────────────────────────────────────
# Maps (STATE, county_lower) → Socrata endpoint config
# Format: {"base_url": ..., "dataset_id": ..., "field_map": {...}}
#
# field_map keys are our canonical field names; values are Socrata column names.
# Minimal required fields: parcel_id, principal_amount
# Optional: address, tax_year, redemption_deadline, total_owed, certificate_number

SOCRATA_REGISTRY: dict[tuple[str, str], dict[str, Any]] = {
    # ── Florida ───────────────────────────────────────────────────────────
    ("FL", "orange"): {
        "base_url": "https://data.ocfl.net",
        "dataset_id": "tax-delinquent-properties",
        "field_map": {
            "parcel_id": "parcel_id",
            "address": "situs_address",
            "tax_year": "tax_year",
            "principal_amount": "face_value",
            "total_owed": "total_due",
            "redemption_deadline": "expiration_date",
            "certificate_number": "certificate_number",
            "lien_status": "status",
        },
    },
    # ── Texas (Harris County uses their own portal) ────────────────────────
    # Harris publishes via LGBS — handled by Tier 2 scraper
    # ── Colorado ──────────────────────────────────────────────────────────
    ("CO", "denver"): {
        "base_url": "https://opendata-geospatialdenver.hub.arcgis.com",
        "dataset_id": "delinquent-real-property",
        "field_map": {
            "parcel_id": "pin",
            "address": "property_address",
            "principal_amount": "amount_due",
            "tax_year": "tax_year",
        },
    },
    # ── Iowa ──────────────────────────────────────────────────────────────
    ("IA", "polk"): {
        "base_url": "https://data.polkcountyiowa.gov",
        "dataset_id": "tax-sale-properties",
        "field_map": {
            "parcel_id": "parcel_number",
            "address": "property_address",
            "principal_amount": "amount",
            "auction_date": "sale_date",
        },
    },
}


def _build_soda_url(base_url: str, dataset_id: str) -> str:
    """Construct a Socrata SODA v2.1 JSON endpoint URL."""
    base = base_url.rstrip("/")
    return f"{base}/resource/{dataset_id}.json"


class SocrataDiscoveryScraper(BaseScraper):
    """Queries a Socrata SODA endpoint to discover delinquent tax records."""

    def __init__(self, *, state: str, county: str) -> None:
        super().__init__()
        self.state = state.upper()
        self.county = county.lower()
        self._config = SOCRATA_REGISTRY.get((self.state, self.county))

    async def scrape(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """Low-level fetch — returns parsed JSON."""
        response = await self._fetch(url, params=params)
        return response.json()

    async def discover(self, *, max_records: int = 5000) -> list[dict[str, Any]]:
        """Fetch all delinquent records up to ``max_records``.

        Returns a list of normalised record dicts using our canonical field names.
        Returns empty list if no Socrata dataset is registered for this county.
        """
        if self._config is None:
            log.debug(
                "no_socrata_dataset",
                state=self.state,
                county=self.county,
            )
            return []

        url = _build_soda_url(self._config["base_url"], self._config["dataset_id"])
        field_map: dict[str, str] = self._config["field_map"]
        page_size = min(max_records, 50_000)

        all_records: list[dict[str, Any]] = []
        offset = 0

        while len(all_records) < max_records:
            params = {
                "$limit": min(page_size, max_records - len(all_records)),
                "$offset": offset,
                "$order": ":id",
            }

            log.debug("fetching_page", url=url, offset=offset)
            raw_page: list[dict[str, Any]] = await self.scrape(url, params=params)

            if not raw_page:
                break   # no more data

            normalised = [self._normalise(row, field_map) for row in raw_page]
            all_records.extend(r for r in normalised if r)
            offset += len(raw_page)

            if len(raw_page) < page_size:
                break   # last page

        log.info("socrata_discovery_done", state=self.state, county=self.county, count=len(all_records))
        return all_records

    # ── Normalisation ─────────────────────────────────────────────────────

    def _normalise(
        self,
        raw: dict[str, Any],
        field_map: dict[str, str],
    ) -> dict[str, Any] | None:
        """Map a raw Socrata row to our canonical field names.

        Returns ``None`` if the record is missing its parcel ID.
        """
        out: dict[str, Any] = {
            "source_url": _build_soda_url(
                self._config["base_url"], self._config["dataset_id"]
            ),
        }

        for canonical, socrata_col in field_map.items():
            value = raw.get(socrata_col)
            if value is None:
                continue

            # Type coercions
            if canonical in ("principal_amount", "total_owed", "opening_bid", "interest_amount"):
                out[canonical] = _to_float(value)
            elif canonical in ("tax_year", "years_delinquent", "post_sale_redemption_days"):
                out[canonical] = _to_int(value)
            elif canonical in ("redemption_deadline", "auction_date", "filing_date"):
                out[canonical] = _to_date(value)
            else:
                out[canonical] = str(value).strip()

        parcel_id = out.get("parcel_id")
        if not parcel_id:
            return None

        # Normalise parcel_id: strip spaces and common separators
        out["parcel_id"] = re.sub(r"[\s\-\./]", "", str(parcel_id)).upper()
        return out


# ── Conversion helpers ────────────────────────────────────────────────────────

def _to_float(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _to_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    raw = str(value).strip()
    # Try ISO format first (most Socrata dates)
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        pass
    # Try MM/DD/YYYY
    try:
        parts = raw.split("/")
        if len(parts) == 3:
            return date(int(parts[2]), int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        pass
    return None
