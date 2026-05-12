"""Unit tests for SocrataDiscoveryScraper (Tier 1 API client).

All HTTP calls are mocked with respx — no real network traffic.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from aloha.scrapers.tier1_apis.socrata import (
    SOCRATA_REGISTRY,
    SocrataDiscoveryScraper,
    _build_soda_url,
    _to_date,
    _to_float,
    _to_int,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _scraper(state: str = "FL", county: str = "orange") -> SocrataDiscoveryScraper:
    s = SocrataDiscoveryScraper(state=state, county=county)
    s._rate_limiter = AsyncMock()
    s._rate_limiter.acquire = AsyncMock()
    return s


# ── URL builder ───────────────────────────────────────────────────────────────

class TestBuildSodaUrl:
    """Tests for _build_soda_url helper."""

    def test_basic(self) -> None:
        url = _build_soda_url("https://data.example.com", "my-dataset")
        assert url == "https://data.example.com/resource/my-dataset.json"

    def test_trailing_slash_stripped(self) -> None:
        url = _build_soda_url("https://data.example.com/", "ds")
        assert url == "https://data.example.com/resource/ds.json"


# ── Type coercion helpers ─────────────────────────────────────────────────────

class TestToFloat:
    """Tests for _to_float."""

    def test_plain_number(self) -> None:
        assert _to_float("1234.56") == 1234.56

    def test_dollar_commas(self) -> None:
        assert _to_float("$12,345.67") == 12345.67

    def test_integer_string(self) -> None:
        assert _to_float("500") == 500.0

    def test_none(self) -> None:
        assert _to_float(None) is None

    def test_non_numeric(self) -> None:
        assert _to_float("N/A") is None

    def test_numeric_type(self) -> None:
        assert _to_float(42.5) == 42.5


class TestToInt:
    """Tests for _to_int."""

    def test_integer_string(self) -> None:
        assert _to_int("2024") == 2024

    def test_none(self) -> None:
        assert _to_int(None) is None

    def test_non_numeric(self) -> None:
        assert _to_int("abc") is None

    def test_numeric_type(self) -> None:
        assert _to_int(10) == 10

    def test_float_string(self) -> None:
        # "2024.0" cannot be parsed by int() directly — returns None
        assert _to_int("2024.0") is None


class TestToDate:
    """Tests for _to_date."""

    def test_iso_format(self) -> None:
        assert _to_date("2025-06-15") == date(2025, 6, 15)

    def test_iso_with_time(self) -> None:
        assert _to_date("2025-06-15T14:30:00") == date(2025, 6, 15)

    def test_mm_dd_yyyy(self) -> None:
        assert _to_date("6/15/2025") == date(2025, 6, 15)

    def test_padded_mm_dd_yyyy(self) -> None:
        assert _to_date("06/15/2025") == date(2025, 6, 15)

    def test_none(self) -> None:
        assert _to_date(None) is None

    def test_empty(self) -> None:
        assert _to_date("") is None

    def test_garbage(self) -> None:
        assert _to_date("not-a-date") is None

    def test_date_passthrough(self) -> None:
        d = date(2025, 1, 1)
        assert _to_date(d) is d


# ── Registry ──────────────────────────────────────────────────────────────────

class TestRegistry:
    """Tests for SOCRATA_REGISTRY static data."""

    def test_florida_orange_registered(self) -> None:
        config = SOCRATA_REGISTRY.get(("FL", "orange"))
        assert config is not None
        assert "base_url" in config
        assert "dataset_id" in config
        assert "field_map" in config

    def test_colorado_denver_registered(self) -> None:
        config = SOCRATA_REGISTRY.get(("CO", "denver"))
        assert config is not None

    def test_iowa_polk_registered(self) -> None:
        config = SOCRATA_REGISTRY.get(("IA", "polk"))
        assert config is not None

    def test_field_map_has_parcel_id(self) -> None:
        for key, config in SOCRATA_REGISTRY.items():
            assert "parcel_id" in config["field_map"], (
                f"Registry entry {key} missing parcel_id in field_map"
            )


# ── Constructor ───────────────────────────────────────────────────────────────

class TestConstructor:
    """Tests for SocrataDiscoveryScraper initialisation."""

    def test_state_uppercased(self) -> None:
        s = _scraper(state="fl")
        assert s.state == "FL"

    def test_county_lowercased(self) -> None:
        s = _scraper(county="Orange")
        assert s.county == "orange"

    def test_config_loaded_for_known_county(self) -> None:
        s = _scraper(state="FL", county="orange")
        assert s._config is not None

    def test_config_none_for_unknown_county(self) -> None:
        s = _scraper(state="XX", county="nonexistent")
        assert s._config is None


# ── Normalisation ─────────────────────────────────────────────────────────────

class TestNormalisation:
    """Tests for the _normalise method."""

    def _make_scraper(self) -> SocrataDiscoveryScraper:
        return _scraper(state="FL", county="orange")

    def test_standard_record(self) -> None:
        s = self._make_scraper()
        field_map = s._config["field_map"]
        raw = {
            "parcel_id": "12-34-56-789",
            "situs_address": "100 Main St",
            "face_value": "$5,000.00",
            "total_due": "$6,200.50",
            "tax_year": "2023",
            "expiration_date": "2026-01-15",
            "certificate_number": "CERT-001",
            "status": "active",
        }
        result = s._normalise(raw, field_map)
        assert result is not None
        assert result["parcel_id"] == "123456789"  # separators stripped
        assert result["address"] == "100 Main St"
        assert result["principal_amount"] == 5000.0
        assert result["total_owed"] == 6200.5
        assert result["tax_year"] == 2023
        assert result["redemption_deadline"] == date(2026, 1, 15)
        assert result["certificate_number"] == "CERT-001"

    def test_parcel_id_normalisation(self) -> None:
        """Parcel IDs have spaces, dashes, dots, and slashes stripped, then uppercased."""
        s = self._make_scraper()
        field_map = s._config["field_map"]
        raw = {"parcel_id": "ab-12.34/56 78"}
        result = s._normalise(raw, field_map)
        assert result is not None
        assert result["parcel_id"] == "AB12345678"

    def test_missing_parcel_id_returns_none(self) -> None:
        s = self._make_scraper()
        field_map = s._config["field_map"]
        raw = {"situs_address": "123 St"}
        result = s._normalise(raw, field_map)
        assert result is None

    def test_none_values_skipped(self) -> None:
        """Fields with None values are not included in output."""
        s = self._make_scraper()
        field_map = s._config["field_map"]
        raw = {"parcel_id": "X", "situs_address": None}
        result = s._normalise(raw, field_map)
        assert result is not None
        assert "address" not in result

    def test_source_url_included(self) -> None:
        s = self._make_scraper()
        field_map = s._config["field_map"]
        raw = {"parcel_id": "X"}
        result = s._normalise(raw, field_map)
        assert result is not None
        assert "source_url" in result
        assert result["source_url"].endswith(".json")


# ── Discover ──────────────────────────────────────────────────────────────────

class TestDiscover:
    """Tests for discover() — pagination and end-to-end with mocked HTTP."""

    @respx.mock
    async def test_single_page(self) -> None:
        s = _scraper()
        url = _build_soda_url(
            s._config["base_url"], s._config["dataset_id"]
        )
        respx.get(url).mock(
            return_value=httpx.Response(200, json=[
                {"parcel_id": "P1", "face_value": "100"},
                {"parcel_id": "P2", "face_value": "200"},
            ])
        )
        records = await s.discover(max_records=100)
        assert len(records) == 2
        assert records[0]["parcel_id"] == "P1"
        await s.close()

    @respx.mock
    async def test_empty_response(self) -> None:
        s = _scraper()
        url = _build_soda_url(
            s._config["base_url"], s._config["dataset_id"]
        )
        respx.get(url).mock(
            return_value=httpx.Response(200, json=[])
        )
        records = await s.discover()
        assert records == []
        await s.close()

    @respx.mock
    async def test_no_dataset_returns_empty(self) -> None:
        """Unregistered county returns empty list without making any HTTP calls."""
        s = _scraper(state="XX", county="nowhere")
        records = await s.discover()
        assert records == []
        await s.close()

    @respx.mock
    async def test_pagination(self) -> None:
        """When first page is full, a second page is fetched."""
        s = _scraper()
        url = _build_soda_url(
            s._config["base_url"], s._config["dataset_id"]
        )
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Return max_records items to trigger next page
                return httpx.Response(200, json=[
                    {"parcel_id": f"P{i}"} for i in range(10)
                ])
            # Second page: fewer items → last page
            return httpx.Response(200, json=[
                {"parcel_id": f"P{i}"} for i in range(10, 13)
            ])

        respx.get(url).mock(side_effect=handler)
        records = await s.discover(max_records=10)
        assert len(records) == 10
        await s.close()

    @respx.mock
    async def test_http_error_propagates(self) -> None:
        """HTTP errors during discover propagate (not caught like auction scrapers)."""
        s = _scraper()
        url = _build_soda_url(
            s._config["base_url"], s._config["dataset_id"]
        )
        respx.get(url).mock(
            return_value=httpx.Response(500, text="Server Error")
        )
        with pytest.raises(httpx.HTTPStatusError):
            await s.discover()
        await s.close()

    @respx.mock
    async def test_skips_records_without_parcel(self) -> None:
        s = _scraper()
        url = _build_soda_url(
            s._config["base_url"], s._config["dataset_id"]
        )
        respx.get(url).mock(
            return_value=httpx.Response(200, json=[
                {"parcel_id": "GOOD"},
                {"situs_address": "no parcel"},
                {"parcel_id": "ALSO-GOOD"},
            ])
        )
        records = await s.discover()
        assert len(records) == 2
        await s.close()

    @respx.mock
    async def test_dollar_amounts_parsed(self) -> None:
        """Verify that dollar amounts like '$1,234.56' are parsed correctly."""
        s = _scraper()
        url = _build_soda_url(
            s._config["base_url"], s._config["dataset_id"]
        )
        respx.get(url).mock(
            return_value=httpx.Response(200, json=[
                {
                    "parcel_id": "P1",
                    "face_value": "$1,234.56",
                    "total_due": "$2,000.00",
                },
            ])
        )
        records = await s.discover()
        assert len(records) == 1
        assert records[0]["principal_amount"] == 1234.56
        assert records[0]["total_owed"] == 2000.0
        await s.close()

    @respx.mock
    async def test_dates_parsed_correctly(self) -> None:
        s = _scraper()
        url = _build_soda_url(
            s._config["base_url"], s._config["dataset_id"]
        )
        respx.get(url).mock(
            return_value=httpx.Response(200, json=[
                {
                    "parcel_id": "P1",
                    "expiration_date": "2026-06-15T00:00:00",
                },
            ])
        )
        records = await s.discover()
        assert len(records) == 1
        assert records[0]["redemption_deadline"] == date(2026, 6, 15)
        await s.close()

    @respx.mock
    async def test_429_rate_limit_retried(self) -> None:
        """429 responses trigger tenacity retries in the base scraper."""
        s = _scraper()
        url = _build_soda_url(
            s._config["base_url"], s._config["dataset_id"]
        )
        route = respx.get(url).mock(
            return_value=httpx.Response(429, text="Rate limited")
        )
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await s.discover()
        assert exc_info.value.response.status_code == 429
        # Retried 3 times (tenacity default)
        assert route.call_count == 3
        await s.close()


# ── Colorado Denver field mapping ─────────────────────────────────────────────

class TestDenverFieldMap:
    """Test that Denver's field map works with its specific column names."""

    @respx.mock
    async def test_denver_record(self) -> None:
        s = _scraper(state="CO", county="denver")
        url = _build_soda_url(
            s._config["base_url"], s._config["dataset_id"]
        )
        respx.get(url).mock(
            return_value=httpx.Response(200, json=[
                {
                    "pin": "0512345678",
                    "property_address": "100 Colfax Ave",
                    "amount_due": "3500.00",
                    "tax_year": "2024",
                },
            ])
        )
        records = await s.discover()
        assert len(records) == 1
        assert records[0]["parcel_id"] == "0512345678"
        assert records[0]["address"] == "100 Colfax Ave"
        assert records[0]["principal_amount"] == 3500.0
        assert records[0]["tax_year"] == 2024
        await s.close()


# ── Iowa Polk field mapping ──────────────────────────────────────────────────

class TestPolkFieldMap:
    """Test Iowa Polk county specific column names."""

    @respx.mock
    async def test_polk_record(self) -> None:
        s = _scraper(state="IA", county="polk")
        url = _build_soda_url(
            s._config["base_url"], s._config["dataset_id"]
        )
        respx.get(url).mock(
            return_value=httpx.Response(200, json=[
                {
                    "parcel_number": "1234567890",
                    "property_address": "200 Grand Ave",
                    "amount": "$1,500.00",
                    "sale_date": "2025-09-01",
                },
            ])
        )
        records = await s.discover()
        assert len(records) == 1
        assert records[0]["parcel_id"] == "1234567890"
        assert records[0]["principal_amount"] == 1500.0
        assert records[0]["auction_date"] == date(2025, 9, 1)
        await s.close()
