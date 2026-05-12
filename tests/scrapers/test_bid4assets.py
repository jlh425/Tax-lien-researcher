"""Unit tests for Bid4Assets auction platform scraper.

All HTTP calls are mocked with respx — no real network traffic.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from aloha.scrapers.auction_platforms.bid4assets import (
    Bid4AssetsScraper,
    _parse_date_str,
    _to_float,
    get_bid4assets_scraper,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _scraper(
    state: str = "FL",
    county: str | None = "orange",
) -> Bid4AssetsScraper:
    s = Bid4AssetsScraper(state=state, county=county)
    # Bypass rate limiter for test speed
    s._rate_limiter = AsyncMock()
    s._rate_limiter.acquire = AsyncMock()
    return s


# ── Factory tests ─────────────────────────────────────────────────────────────

class TestFactory:
    """Tests for get_bid4assets_scraper factory function."""

    def test_returns_scraper_instance(self) -> None:
        s = get_bid4assets_scraper("FL", "orange")
        assert isinstance(s, Bid4AssetsScraper)
        assert s.state == "FL"
        assert s.county == "orange"

    def test_state_uppercased(self) -> None:
        s = get_bid4assets_scraper("fl")
        assert s.state == "FL"

    def test_county_lowercased(self) -> None:
        s = get_bid4assets_scraper("FL", "Orange")
        assert s.county == "orange"

    def test_county_none_allowed(self) -> None:
        s = get_bid4assets_scraper("TX")
        assert s.county is None


# ── Date parsing ──────────────────────────────────────────────────────────────

class TestParseDateStr:
    """Tests for _parse_date_str helper."""

    def test_iso_format(self) -> None:
        assert _parse_date_str("2025-03-15") == "2025-03-15"

    def test_iso_with_time_truncated(self) -> None:
        assert _parse_date_str("2025-03-15T14:30:00Z") == "2025-03-15"

    def test_mm_dd_yyyy(self) -> None:
        assert _parse_date_str("3/15/2025") == "2025-03-15"

    def test_mm_dd_yyyy_padded(self) -> None:
        assert _parse_date_str("03/15/2025") == "2025-03-15"

    def test_none_input(self) -> None:
        assert _parse_date_str(None) is None

    def test_empty_string(self) -> None:
        assert _parse_date_str("") is None

    def test_garbage_returns_none(self) -> None:
        assert _parse_date_str("not-a-date") is None

    def test_numeric_input(self) -> None:
        # Numeric timestamp-like value — should return None (not ISO)
        assert _parse_date_str(1234567890) is None


# ── Dollar parsing ────────────────────────────────────────────────────────────

class TestToFloat:
    """Tests for _to_float helper."""

    def test_plain_number(self) -> None:
        assert _to_float("1234.56") == 1234.56

    def test_dollar_sign(self) -> None:
        assert _to_float("$1,234.56") == 1234.56

    def test_integer(self) -> None:
        assert _to_float("500") == 500.0

    def test_none(self) -> None:
        assert _to_float(None) is None

    def test_non_numeric(self) -> None:
        assert _to_float("N/A") is None

    def test_numeric_type(self) -> None:
        assert _to_float(42) == 42.0

    def test_commas_stripped(self) -> None:
        assert _to_float("$10,000") == 10000.0

    def test_whitespace_stripped(self) -> None:
        assert _to_float("  $500.00  ") == 500.0


# ── Normalisation ─────────────────────────────────────────────────────────────

class TestNormalisation:
    """Tests for _normalise_b4a."""

    def test_standard_record(self) -> None:
        s = _scraper()
        raw = {
            "parcel_id": "12-34-56-789",
            "county": "Orange",
            "auction_date": "2025-06-15",
            "starting_bid": "$5,000.00",
            "address": "123 Main St",
            "url": "/auction/42",
        }
        result = s._normalise_b4a(raw)
        assert result is not None
        assert result["parcel_id"] == "12-34-56-789"
        assert result["state"] == "FL"
        assert result["county"] == "orange"
        assert result["auction_date"] == "2025-06-15"
        assert result["opening_bid"] == 5000.0
        assert result["address"] == "123 Main St"
        assert result["auction_url"] == "https://www.bid4assets.com/auction/42"
        assert result["auction_platform"] == "bid4assets"
        assert result["instrument_type"] == "tax_deed"

    def test_camelcase_fields(self) -> None:
        s = _scraper()
        raw = {
            "parcelId": "ABC-123",
            "auctionDate": "06/15/2025",
            "startingBid": 3500,
        }
        result = s._normalise_b4a(raw)
        assert result is not None
        assert result["parcel_id"] == "ABC-123"
        assert result["auction_date"] == "2025-06-15"
        assert result["opening_bid"] == 3500.0

    def test_apn_alias(self) -> None:
        s = _scraper()
        raw = {"apn": "  lower-apn  "}
        result = s._normalise_b4a(raw)
        assert result is not None
        assert result["parcel_id"] == "LOWER-APN"

    def test_folio_alias(self) -> None:
        s = _scraper()
        raw = {"folio": "5678901234"}
        result = s._normalise_b4a(raw)
        assert result is not None
        assert result["parcel_id"] == "5678901234"

    def test_no_parcel_id_returns_none(self) -> None:
        s = _scraper()
        raw = {"address": "123 Main St", "starting_bid": "$1,000"}
        result = s._normalise_b4a(raw)
        assert result is None

    def test_absolute_url_preserved(self) -> None:
        s = _scraper()
        raw = {"parcel_id": "X", "url": "https://other.com/auction/1"}
        result = s._normalise_b4a(raw)
        assert result is not None
        assert result["auction_url"] == "https://other.com/auction/1"

    def test_relative_url_gets_base(self) -> None:
        s = _scraper()
        raw = {"parcel_id": "X", "link": "/details/99"}
        result = s._normalise_b4a(raw)
        assert result is not None
        assert result["auction_url"] == "https://www.bid4assets.com/details/99"

    def test_county_fallback_to_constructor(self) -> None:
        s = _scraper(county="seminole")
        raw = {"parcel_id": "X"}
        result = s._normalise_b4a(raw)
        assert result is not None
        assert result["county"] == "seminole"

    def test_missing_optional_fields(self) -> None:
        s = _scraper()
        raw = {"parcel_id": "BARE-MINIMUM"}
        result = s._normalise_b4a(raw)
        assert result is not None
        assert result["address"] is None
        assert result["auction_date"] is None
        assert result["opening_bid"] is None
        assert result["auction_url"] is None


# ── Discover (integration with mocked HTTP) ──────────────────────────────────

class TestDiscover:
    """Tests for the discover() pagination and parsing logic."""

    @respx.mock
    async def test_discover_dict_response_with_auctions_key(self) -> None:
        s = _scraper()
        respx.get("https://www.bid4assets.com/api/auctions").mock(
            return_value=httpx.Response(200, json={
                "auctions": [
                    {"parcel_id": "A1", "starting_bid": "$100"},
                    {"parcel_id": "A2", "starting_bid": "$200"},
                ],
            })
        )
        records = await s.discover(max_records=10)
        assert len(records) == 2
        assert records[0]["parcel_id"] == "A1"
        assert records[1]["parcel_id"] == "A2"
        await s.close()

    @respx.mock
    async def test_discover_dict_response_with_results_key(self) -> None:
        s = _scraper()
        respx.get("https://www.bid4assets.com/api/auctions").mock(
            return_value=httpx.Response(200, json={
                "results": [{"parcel_id": "R1"}],
            })
        )
        records = await s.discover()
        assert len(records) == 1
        assert records[0]["parcel_id"] == "R1"
        await s.close()

    @respx.mock
    async def test_discover_dict_response_with_data_key(self) -> None:
        s = _scraper()
        respx.get("https://www.bid4assets.com/api/auctions").mock(
            return_value=httpx.Response(200, json={
                "data": [{"parcel_id": "D1"}],
            })
        )
        records = await s.discover()
        assert len(records) == 1
        await s.close()

    @respx.mock
    async def test_discover_list_response(self) -> None:
        s = _scraper()
        respx.get("https://www.bid4assets.com/api/auctions").mock(
            return_value=httpx.Response(200, json=[
                {"parcel_id": "L1"},
                {"parcel_id": "L2"},
            ])
        )
        records = await s.discover()
        assert len(records) == 2
        await s.close()

    @respx.mock
    async def test_discover_empty_response(self) -> None:
        s = _scraper()
        respx.get("https://www.bid4assets.com/api/auctions").mock(
            return_value=httpx.Response(200, json={"auctions": []})
        )
        records = await s.discover()
        assert records == []
        await s.close()

    @respx.mock
    async def test_discover_malformed_response(self) -> None:
        """Non-JSON-like response body should yield empty list, not crash."""
        s = _scraper()
        respx.get("https://www.bid4assets.com/api/auctions").mock(
            return_value=httpx.Response(200, json="unexpected-string")
        )
        records = await s.discover()
        assert records == []
        await s.close()

    @respx.mock
    async def test_discover_http_error_returns_empty(self) -> None:
        """HTTP errors during discover are caught and yield empty list."""
        s = _scraper()
        respx.get("https://www.bid4assets.com/api/auctions").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        records = await s.discover()
        assert records == []
        await s.close()

    @respx.mock
    async def test_discover_network_error_returns_empty(self) -> None:
        s = _scraper()
        respx.get("https://www.bid4assets.com/api/auctions").mock(
            side_effect=httpx.ConnectTimeout("Connection timed out")
        )
        records = await s.discover()
        assert records == []
        await s.close()

    @respx.mock
    async def test_discover_pagination(self) -> None:
        """When first page is full (100 items), a second page is requested."""
        s = _scraper()
        page1 = [{"parcel_id": f"P{i}"} for i in range(100)]
        page2 = [{"parcel_id": f"P{i}"} for i in range(100, 110)]

        call_count = 0

        def route_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json={"auctions": page1})
            return httpx.Response(200, json={"auctions": page2})

        respx.get("https://www.bid4assets.com/api/auctions").mock(
            side_effect=route_handler
        )
        records = await s.discover(max_records=500)
        assert len(records) == 110
        assert call_count == 2
        await s.close()

    @respx.mock
    async def test_discover_respects_max_records(self) -> None:
        """Records are truncated to max_records."""
        s = _scraper()
        respx.get("https://www.bid4assets.com/api/auctions").mock(
            return_value=httpx.Response(200, json={
                "auctions": [{"parcel_id": f"P{i}"} for i in range(50)],
            })
        )
        records = await s.discover(max_records=5)
        assert len(records) == 5
        await s.close()

    @respx.mock
    async def test_discover_skips_records_without_parcel_id(self) -> None:
        s = _scraper()
        respx.get("https://www.bid4assets.com/api/auctions").mock(
            return_value=httpx.Response(200, json={
                "auctions": [
                    {"parcel_id": "GOOD"},
                    {"address": "No parcel ID here"},
                    {"parcel_id": "ALSO-GOOD"},
                ],
            })
        )
        records = await s.discover()
        assert len(records) == 2
        await s.close()

    @respx.mock
    async def test_discover_includes_county_param(self) -> None:
        """When county is set, it should be sent as a query parameter."""
        s = _scraper(county="orange")
        route = respx.get("https://www.bid4assets.com/api/auctions").mock(
            return_value=httpx.Response(200, json={"auctions": []})
        )
        await s.discover()
        assert route.called
        # Verify county was in params
        request = route.calls[0].request
        assert b"county=orange" in request.url.raw_path
        await s.close()
