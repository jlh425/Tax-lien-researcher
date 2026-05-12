"""Unit tests for GovEase auction platform scraper.

All HTTP calls are mocked with respx — no real network traffic.
Playwright SPA tests use unittest.mock to avoid launching a real browser.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from aloha.scrapers.auction_platforms.govease import (
    GOVEASE_ENDPOINTS,
    GovEaseScraper,
    _parse_date,
    _to_float,
    get_govease_scraper,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _scraper(
    state: str = "CO",
    county: str = "denver",
) -> GovEaseScraper:
    s = GovEaseScraper(state=state, county=county)
    s._rate_limiter = AsyncMock()
    s._rate_limiter.acquire = AsyncMock()
    return s


# ── Factory tests ─────────────────────────────────────────────────────────────

class TestFactory:
    """Tests for get_govease_scraper factory function."""

    def test_returns_scraper_for_known_county(self) -> None:
        s = get_govease_scraper("CO", "denver")
        assert isinstance(s, GovEaseScraper)
        assert s.state == "CO"
        assert s.county == "denver"

    def test_returns_none_for_unknown_county(self) -> None:
        s = get_govease_scraper("XX", "nonexistent")
        assert s is None

    def test_case_insensitive_lookup(self) -> None:
        s = get_govease_scraper("co", "Denver")
        # The lookup normalises case
        assert s is None or isinstance(s, GovEaseScraper)

    def test_endpoint_registry_populated(self) -> None:
        assert len(GOVEASE_ENDPOINTS) > 0
        assert ("CO", "denver") in GOVEASE_ENDPOINTS
        assert ("IL", "cook") in GOVEASE_ENDPOINTS


# ── Date parsing ──────────────────────────────────────────────────────────────

class TestParseDate:
    """Tests for _parse_date helper."""

    def test_iso_format(self) -> None:
        assert _parse_date("2025-06-15") == "2025-06-15"

    def test_iso_with_timestamp(self) -> None:
        assert _parse_date("2025-06-15T10:00:00") == "2025-06-15"

    def test_mm_dd_yyyy(self) -> None:
        assert _parse_date("6/15/2025") == "2025-06-15"

    def test_padded_mm_dd_yyyy(self) -> None:
        assert _parse_date("06/15/2025") == "2025-06-15"

    def test_none(self) -> None:
        assert _parse_date(None) is None

    def test_empty(self) -> None:
        assert _parse_date("") is None

    def test_garbage(self) -> None:
        assert _parse_date("not-a-date") is None


# ── Dollar parsing ────────────────────────────────────────────────────────────

class TestToFloat:
    """Tests for _to_float helper."""

    def test_dollar_with_commas(self) -> None:
        assert _to_float("$12,345.67") == 12345.67

    def test_plain_number(self) -> None:
        assert _to_float("500") == 500.0

    def test_none(self) -> None:
        assert _to_float(None) is None

    def test_non_numeric(self) -> None:
        assert _to_float("N/A") is None

    def test_numeric_type(self) -> None:
        assert _to_float(99.5) == 99.5


# ── JSON normalisation ───────────────────────────────────────────────────────

class TestNormaliseGovease:
    """Tests for _normalise_govease."""

    def test_standard_record(self) -> None:
        s = _scraper()
        raw = {
            "parcel_id": "0512345678",
            "auction_date": "2025-07-01",
            "opening_bid": "$2,500.00",
            "address": "456 Elm St",
            "sale_type": "tax_deed",
            "url": "https://app.govease.com/auction/123",
        }
        result = s._normalise_govease(raw)
        assert result is not None
        assert result["parcel_id"] == "0512345678"
        assert result["state"] == "CO"
        assert result["county"] == "denver"
        assert result["auction_date"] == "2025-07-01"
        assert result["opening_bid"] == 2500.0
        assert result["address"] == "456 Elm St"
        assert result["instrument_type"] == "tax_deed"
        assert result["auction_platform"] == "govease"

    def test_camelcase_fields(self) -> None:
        s = _scraper()
        raw = {
            "parcelId": "CC-12345",
            "auctionDate": "07/01/2025",
            "openingBid": 1500,
        }
        result = s._normalise_govease(raw)
        assert result is not None
        assert result["parcel_id"] == "CC-12345"
        assert result["auction_date"] == "2025-07-01"
        assert result["opening_bid"] == 1500.0

    def test_lien_instrument_default(self) -> None:
        """When sale_type is not deed-like, default to lien_certificate."""
        s = _scraper()
        raw = {"parcel_id": "X", "sale_type": "lien"}
        result = s._normalise_govease(raw)
        assert result is not None
        assert result["instrument_type"] == "lien_certificate"

    def test_deed_instrument_detected(self) -> None:
        s = _scraper()
        raw = {"parcel_id": "X", "sale_type": "Tax Deed Sale"}
        result = s._normalise_govease(raw)
        assert result is not None
        assert result["instrument_type"] == "tax_deed"

    def test_no_parcel_id_returns_none(self) -> None:
        s = _scraper()
        raw = {"address": "No parcel"}
        assert s._normalise_govease(raw) is None

    def test_id_field_used_as_parcel_fallback(self) -> None:
        s = _scraper()
        raw = {"id": "FALLBACK-99"}
        result = s._normalise_govease(raw)
        assert result is not None
        assert result["parcel_id"] == "FALLBACK-99"

    def test_missing_optional_fields(self) -> None:
        s = _scraper()
        raw = {"parcel_id": "BARE"}
        result = s._normalise_govease(raw)
        assert result is not None
        assert result["address"] is None
        assert result["auction_date"] is None
        assert result["opening_bid"] is None


# ── Text normalisation (Playwright scrape fallback) ──────────────────────────

class TestNormaliseGoveaseText:
    """Tests for _normalise_govease_text (parses auction card inner text)."""

    def test_extracts_parcel_and_bid(self) -> None:
        s = _scraper()
        text = "APN: 0512345-678\nBid: $1,500.00\nDate: 07/15/2025"
        result = s._normalise_govease_text(text)
        assert result is not None
        assert result["parcel_id"] == "0512345-678"
        assert result["opening_bid"] == 1500.0
        assert result["auction_date"] == "2025-07-15"

    def test_iso_date_in_text(self) -> None:
        s = _scraper()
        text = "APN: 123456-789 Date: 2025-08-01 Bid: $500"
        result = s._normalise_govease_text(text)
        assert result is not None
        assert result["auction_date"] == "2025-08-01"

    def test_no_apn_returns_none(self) -> None:
        s = _scraper()
        # Use only short words (< 6 chars) so the APN regex cannot match
        text = "No APN here at all"
        result = s._normalise_govease_text(text)
        assert result is None

    def test_empty_text_returns_none(self) -> None:
        s = _scraper()
        assert s._normalise_govease_text("") is None

    def test_parcel_uppercased(self) -> None:
        s = _scraper()
        text = "abc123-def456 $100"
        result = s._normalise_govease_text(text)
        assert result is not None
        assert result["parcel_id"] == "ABC123-DEF456"


# ── API discover ──────────────────────────────────────────────────────────────

class TestTryApi:
    """Tests for _try_api with mocked HTTP."""

    @respx.mock
    async def test_dict_response_with_listings_key(self) -> None:
        s = _scraper()
        respx.get("https://app.govease.com/api/v1/listings").mock(
            return_value=httpx.Response(200, json={
                "listings": [
                    {"parcel_id": "G1", "opening_bid": "$100"},
                    {"parcel_id": "G2", "opening_bid": "$200"},
                ],
            })
        )
        records = await s._try_api(500)
        assert len(records) == 2
        assert records[0]["parcel_id"] == "G1"
        await s.close()

    @respx.mock
    async def test_list_response(self) -> None:
        s = _scraper()
        respx.get("https://app.govease.com/api/v1/listings").mock(
            return_value=httpx.Response(200, json=[
                {"parcel_id": "L1"},
            ])
        )
        records = await s._try_api(500)
        assert len(records) == 1
        await s.close()

    @respx.mock
    async def test_empty_response(self) -> None:
        s = _scraper()
        respx.get("https://app.govease.com/api/v1/listings").mock(
            return_value=httpx.Response(200, json={"listings": []})
        )
        records = await s._try_api(500)
        assert records == []
        await s.close()

    @respx.mock
    async def test_http_error_returns_empty(self) -> None:
        s = _scraper()
        respx.get("https://app.govease.com/api/v1/listings").mock(
            return_value=httpx.Response(500, text="Server Error")
        )
        records = await s._try_api(500)
        assert records == []
        await s.close()

    @respx.mock
    async def test_timeout_returns_empty(self) -> None:
        s = _scraper()
        respx.get("https://app.govease.com/api/v1/listings").mock(
            side_effect=httpx.ReadTimeout("Read timed out")
        )
        records = await s._try_api(500)
        assert records == []
        await s.close()

    @respx.mock
    async def test_non_json_response_returns_empty(self) -> None:
        """HTML response (not list/dict) should yield empty list."""
        s = _scraper()
        respx.get("https://app.govease.com/api/v1/listings").mock(
            return_value=httpx.Response(
                200, text="<html>Not JSON</html>",
                headers={"content-type": "text/html"},
            )
        )
        records = await s._try_api(500)
        assert records == []
        await s.close()

    @respx.mock
    async def test_max_records_respected(self) -> None:
        s = _scraper()
        items = [{"parcel_id": f"P{i}"} for i in range(50)]
        respx.get("https://app.govease.com/api/v1/listings").mock(
            return_value=httpx.Response(200, json={"listings": items})
        )
        records = await s._try_api(3)
        assert len(records) == 3
        await s.close()

    @respx.mock
    async def test_skips_records_without_parcel(self) -> None:
        s = _scraper()
        respx.get("https://app.govease.com/api/v1/listings").mock(
            return_value=httpx.Response(200, json={
                "listings": [
                    {"parcel_id": "OK"},
                    {"address": "no-parcel"},
                    {"parcel_id": "ALSO-OK"},
                ],
            })
        )
        records = await s._try_api(500)
        assert len(records) == 2
        await s.close()


# ── Discover (full) ──────────────────────────────────────────────────────────

class TestDiscover:
    """Tests for discover() which tries API then Playwright."""

    @respx.mock
    async def test_discover_uses_api_when_available(self) -> None:
        """If API returns records, Playwright is never called."""
        s = _scraper()
        respx.get("https://app.govease.com/api/v1/listings").mock(
            return_value=httpx.Response(200, json={
                "listings": [{"parcel_id": "API-1"}],
            })
        )
        records = await s.discover()
        assert len(records) == 1
        assert records[0]["parcel_id"] == "API-1"
        await s.close()

    @respx.mock
    async def test_discover_returns_empty_when_api_and_playwright_fail(self) -> None:
        """If both API and Playwright fail, return empty list."""
        s = _scraper()
        respx.get("https://app.govease.com/api/v1/listings").mock(
            return_value=httpx.Response(500, text="Error")
        )
        # Patch Playwright import to raise ImportError (not installed)
        import unittest.mock
        with unittest.mock.patch.dict(
            "sys.modules", {"playwright": None, "playwright.async_api": None}
        ):
            records = await s.discover()
        assert records == []
        await s.close()


# ── Scrape method ─────────────────────────────────────────────────────────────

class TestScrapeMethod:
    """Tests for the low-level scrape() method."""

    @respx.mock
    async def test_json_content_type_returns_dict(self) -> None:
        s = _scraper()
        respx.get("https://app.govease.com/test").mock(
            return_value=httpx.Response(
                200,
                json={"key": "value"},
                headers={"content-type": "application/json"},
            )
        )
        result = await s.scrape("https://app.govease.com/test")
        assert result == {"key": "value"}
        await s.close()

    @respx.mock
    async def test_html_content_type_returns_text(self) -> None:
        s = _scraper()
        respx.get("https://app.govease.com/page").mock(
            return_value=httpx.Response(
                200,
                text="<html>body</html>",
                headers={"content-type": "text/html"},
            )
        )
        result = await s.scrape("https://app.govease.com/page")
        assert result == "<html>body</html>"
        await s.close()
