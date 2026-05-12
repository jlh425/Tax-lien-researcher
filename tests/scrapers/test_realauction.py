"""Unit tests for RealAuction (realtaxdeed.com) scraper.

All HTTP calls are mocked with respx — no real network traffic.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from aloha.scrapers.auction_platforms.realauction import (
    REALAUCTION_ENDPOINTS,
    RealAuctionScraper,
    _parse_date,
    _to_float,
    get_realauction_scraper,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _scraper(
    subdomain: str = "orange",
    state: str = "FL",
    county: str = "orange",
) -> RealAuctionScraper:
    s = RealAuctionScraper(subdomain=subdomain, state=state, county=county)
    s._rate_limiter = AsyncMock()
    s._rate_limiter.acquire = AsyncMock()
    return s


# ── Factory tests ─────────────────────────────────────────────────────────────

class TestFactory:
    """Tests for get_realauction_scraper factory function."""

    def test_returns_scraper_for_known_county(self) -> None:
        s = get_realauction_scraper("FL", "orange")
        assert isinstance(s, RealAuctionScraper)
        assert s.state == "FL"
        assert s.county == "orange"
        assert s.subdomain == "orange"

    def test_returns_none_for_unknown_county(self) -> None:
        s = get_realauction_scraper("XX", "nonexistent")
        assert s is None

    def test_case_insensitive_lookup(self) -> None:
        s = get_realauction_scraper("fl", "Orange")
        assert isinstance(s, RealAuctionScraper)

    def test_endpoint_registry_populated(self) -> None:
        assert len(REALAUCTION_ENDPOINTS) > 0
        assert ("FL", "orange") in REALAUCTION_ENDPOINTS
        assert ("FL", "hillsborough") in REALAUCTION_ENDPOINTS

    def test_palm_beach_subdomain_mapping(self) -> None:
        """Palm-beach maps to 'palmbeach' subdomain (no dash)."""
        s = get_realauction_scraper("FL", "palm-beach")
        assert s is not None
        assert s.subdomain == "palmbeach"


# ── Date parsing ──────────────────────────────────────────────────────────────

class TestParseDate:
    """Tests for _parse_date helper."""

    def test_iso_format(self) -> None:
        assert _parse_date("2025-08-20") == "2025-08-20"

    def test_iso_with_time(self) -> None:
        assert _parse_date("2025-08-20T09:00:00") == "2025-08-20"

    def test_mm_dd_yyyy(self) -> None:
        assert _parse_date("8/20/2025") == "2025-08-20"

    def test_padded_mm_dd_yyyy(self) -> None:
        assert _parse_date("08/20/2025") == "2025-08-20"

    def test_none(self) -> None:
        assert _parse_date(None) is None

    def test_empty(self) -> None:
        assert _parse_date("") is None

    def test_garbage(self) -> None:
        assert _parse_date("invalid") is None


# ── Dollar parsing ────────────────────────────────────────────────────────────

class TestToFloat:
    """Tests for _to_float helper."""

    def test_dollar_commas(self) -> None:
        assert _to_float("$25,000.00") == 25000.0

    def test_plain_int(self) -> None:
        assert _to_float("1000") == 1000.0

    def test_none(self) -> None:
        assert _to_float(None) is None

    def test_non_numeric(self) -> None:
        assert _to_float("TBD") is None


# ── Response parsing ─────────────────────────────────────────────────────────

class TestParseResponse:
    """Tests for _parse_response — handles JSON dict, list, and HTML."""

    def test_list_response(self) -> None:
        s = _scraper()
        data = [{"ACCOUNTNO": "123"}, {"ACCOUNTNO": "456"}]
        result = s._parse_response(data, date.today())
        assert len(result) == 2

    def test_dict_with_auctions_key(self) -> None:
        s = _scraper()
        data = {"AUCTIONS": [{"ACCOUNTNO": "A1"}]}
        result = s._parse_response(data, date.today())
        assert len(result) == 1

    def test_dict_with_lowercase_auctions_key(self) -> None:
        s = _scraper()
        data = {"auctions": [{"ACCOUNTNO": "A2"}]}
        result = s._parse_response(data, date.today())
        assert len(result) == 1

    def test_dict_with_results_key(self) -> None:
        s = _scraper()
        data = {"results": [{"ACCOUNTNO": "R1"}]}
        result = s._parse_response(data, date.today())
        assert len(result) == 1

    def test_dict_with_data_key(self) -> None:
        s = _scraper()
        data = {"data": [{"ACCOUNTNO": "D1"}]}
        result = s._parse_response(data, date.today())
        assert len(result) == 1

    def test_empty_dict_returns_empty(self) -> None:
        s = _scraper()
        result = s._parse_response({}, date.today())
        assert result == []

    def test_html_with_embedded_json(self) -> None:
        s = _scraper()
        html = '<html><script>var data = [{"ACCOUNTNO": "HTML1"}];</script></html>'
        result = s._parse_response(html, date.today())
        assert len(result) == 1
        assert result[0]["ACCOUNTNO"] == "HTML1"

    def test_html_without_json_returns_empty(self) -> None:
        s = _scraper()
        html = "<html><body>No data here</body></html>"
        result = s._parse_response(html, date.today())
        assert result == []

    def test_non_parseable_type_returns_empty(self) -> None:
        s = _scraper()
        result = s._parse_response(42, date.today())  # type: ignore[arg-type]
        assert result == []


# ── Normalisation ─────────────────────────────────────────────────────────────

class TestNormaliseRealauction:
    """Tests for _normalise_realauction."""

    def test_standard_record(self) -> None:
        s = _scraper()
        raw = {
            "ACCOUNTNO": "12-3456-7890",
            "SITUSADDR1": "100 Pine Ave",
            "SITUSADDR2": "Unit 5",
            "STARTINGBID": "$15,000.00",
            "AUCTIONDATE": "09/15/2025",
            "AUCTIONID": "42",
        }
        result = s._normalise_realauction(raw, date(2025, 9, 15))
        assert result is not None
        assert result["parcel_id"] == "12-3456-7890"
        assert result["state"] == "FL"
        assert result["county"] == "orange"
        assert result["address"] == "100 Pine Ave Unit 5"
        assert result["opening_bid"] == 15000.0
        assert result["auction_date"] == "2025-09-15"
        assert result["auction_platform"] == "realauction"
        assert "AID=42" in result["auction_url"]

    def test_parcelid_field_alias(self) -> None:
        s = _scraper()
        raw = {"ParcelID": "abc-123"}
        result = s._normalise_realauction(raw, date(2025, 1, 1))
        assert result is not None
        assert result["parcel_id"] == "ABC-123"

    def test_folio_field_alias(self) -> None:
        s = _scraper()
        raw = {"FOLIO": "98765"}
        result = s._normalise_realauction(raw, date(2025, 1, 1))
        assert result is not None
        assert result["parcel_id"] == "98765"

    def test_no_parcel_returns_none(self) -> None:
        s = _scraper()
        raw = {"SITUSADDR1": "123 St"}
        result = s._normalise_realauction(raw, date(2025, 1, 1))
        assert result is None

    def test_fallback_auction_date(self) -> None:
        """When AUCTIONDATE is missing, fall back to the passed-in date."""
        s = _scraper()
        raw = {"ACCOUNTNO": "X"}
        result = s._normalise_realauction(raw, date(2025, 3, 1))
        assert result is not None
        assert result["auction_date"] == "2025-03-01"

    def test_no_auction_id_means_no_url(self) -> None:
        s = _scraper()
        raw = {"ACCOUNTNO": "X"}
        result = s._normalise_realauction(raw, date(2025, 1, 1))
        assert result is not None
        assert result["auction_url"] is None

    def test_address_combining(self) -> None:
        """addr1 + addr2 are concatenated."""
        s = _scraper()
        raw = {"ACCOUNTNO": "X", "SITUSADDR1": "100 Main", "SITUSADDR2": "Apt 3B"}
        result = s._normalise_realauction(raw, date(2025, 1, 1))
        assert result is not None
        assert result["address"] == "100 Main Apt 3B"

    def test_empty_address_becomes_none(self) -> None:
        s = _scraper()
        raw = {"ACCOUNTNO": "X"}
        result = s._normalise_realauction(raw, date(2025, 1, 1))
        assert result is not None
        assert result["address"] is None


# ── Scrape method ─────────────────────────────────────────────────────────────

class TestScrapeMethod:
    """Tests for the low-level scrape() method."""

    @respx.mock
    async def test_json_content_type_returns_parsed(self) -> None:
        s = _scraper()
        respx.get("https://orange.realtaxdeed.com/test").mock(
            return_value=httpx.Response(
                200,
                json={"key": "value"},
                headers={"content-type": "application/json"},
            )
        )
        result = await s.scrape("https://orange.realtaxdeed.com/test")
        assert result == {"key": "value"}
        await s.close()

    @respx.mock
    async def test_html_content_type_returns_text(self) -> None:
        s = _scraper()
        respx.get("https://orange.realtaxdeed.com/page").mock(
            return_value=httpx.Response(
                200,
                text="<html>body</html>",
                headers={"content-type": "text/html"},
            )
        )
        result = await s.scrape("https://orange.realtaxdeed.com/page")
        assert result == "<html>body</html>"
        await s.close()


# ── Discover ──────────────────────────────────────────────────────────────────

class TestDiscover:
    """Tests for discover() — iterates weekly dates, parses responses."""

    @respx.mock
    async def test_discover_collects_records_across_weeks(self) -> None:
        """Discover iterates up to 13 weeks of dates."""
        s = _scraper()
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return httpx.Response(
                    200,
                    json=[{"ACCOUNTNO": f"ACC-{call_count}"}],
                    headers={"content-type": "application/json"},
                )
            return httpx.Response(
                200,
                json=[],
                headers={"content-type": "application/json"},
            )

        respx.get("https://orange.realtaxdeed.com/index.cfm").mock(
            side_effect=handler
        )
        records = await s.discover(max_records=500)
        assert len(records) == 2
        assert records[0]["parcel_id"] == "ACC-1"
        await s.close()

    @respx.mock
    async def test_discover_empty_when_all_pages_empty(self) -> None:
        s = _scraper()
        respx.get("https://orange.realtaxdeed.com/index.cfm").mock(
            return_value=httpx.Response(
                200, json=[], headers={"content-type": "application/json"}
            )
        )
        records = await s.discover()
        assert records == []
        await s.close()

    @respx.mock
    async def test_discover_http_error_continues(self) -> None:
        """HTTP errors on one date are skipped; other dates are still tried."""
        s = _scraper()
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(500, text="Error")
            if call_count == 2:
                return httpx.Response(
                    200,
                    json=[{"ACCOUNTNO": "RECOVERED"}],
                    headers={"content-type": "application/json"},
                )
            return httpx.Response(
                200, json=[], headers={"content-type": "application/json"}
            )

        respx.get("https://orange.realtaxdeed.com/index.cfm").mock(
            side_effect=handler
        )
        records = await s.discover(max_records=500)
        # At least one successful record from week 2
        assert any(r["parcel_id"] == "RECOVERED" for r in records)
        await s.close()

    @respx.mock
    async def test_discover_respects_max_records(self) -> None:
        s = _scraper()
        respx.get("https://orange.realtaxdeed.com/index.cfm").mock(
            return_value=httpx.Response(
                200,
                json=[{"ACCOUNTNO": f"A-{i}"} for i in range(20)],
                headers={"content-type": "application/json"},
            )
        )
        records = await s.discover(max_records=5)
        assert len(records) <= 5
        await s.close()

    @respx.mock
    async def test_discover_network_timeout_continues(self) -> None:
        """Network timeouts are caught per-date and do not abort the whole discover."""
        s = _scraper()
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectTimeout("timeout")
            if call_count == 2:
                return httpx.Response(
                    200,
                    json=[{"ACCOUNTNO": "AFTER-TIMEOUT"}],
                    headers={"content-type": "application/json"},
                )
            return httpx.Response(
                200, json=[], headers={"content-type": "application/json"}
            )

        respx.get("https://orange.realtaxdeed.com/index.cfm").mock(
            side_effect=handler
        )
        records = await s.discover(max_records=500)
        assert any(r["parcel_id"] == "AFTER-TIMEOUT" for r in records)
        await s.close()

    @respx.mock
    async def test_discover_passes_correct_params(self) -> None:
        """Verify that discover sends zaction, Zmethod, AUCTIONDATE, myDate."""
        s = _scraper()
        route = respx.get("https://orange.realtaxdeed.com/index.cfm").mock(
            return_value=httpx.Response(
                200, json=[], headers={"content-type": "application/json"}
            )
        )
        await s.discover()
        # At least one call should have been made
        assert route.called
        first_request = route.calls[0].request
        url_str = str(first_request.url)
        assert "zaction=AUCTION" in url_str
        assert "Zmethod=PREVIEW" in url_str
        assert "AUCTIONDATE=" in url_str
        assert "myDate=" in url_str
        await s.close()
