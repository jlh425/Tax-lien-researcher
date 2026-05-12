"""Unit tests for ArcGIS REST API scraper (parcel query + map export).

All HTTP calls are mocked with respx — no real network traffic.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from aloha.scrapers.tier1_apis.arcgis import (
    ARCGIS_PARCEL_LAYERS,
    ArcGISMapExporter,
    ArcGISParcelScraper,
    _pick,
    _to_float,
    _to_int,
    get_arcgis_parcel_url,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

_TEST_SERVICE = "https://gis.example.gov/arcgis/rest/services/Parcels/FeatureServer/0"


def _scraper(service_url: str = _TEST_SERVICE) -> ArcGISParcelScraper:
    s = ArcGISParcelScraper(service_url=service_url)
    s._rate_limiter = AsyncMock()
    s._rate_limiter.acquire = AsyncMock()
    return s


# ── Registry tests ────────────────────────────────────────────────────────────

class TestRegistry:
    """Tests for ARCGIS_PARCEL_LAYERS registry and get_arcgis_parcel_url."""

    def test_natrona_registered(self) -> None:
        url = get_arcgis_parcel_url("WY", "natrona")
        assert url is not None
        assert "arcgis" in url.lower()

    def test_unknown_county_returns_none(self) -> None:
        url = get_arcgis_parcel_url("XX", "nonexistent")
        assert url is None

    def test_case_insensitive_lookup(self) -> None:
        url = get_arcgis_parcel_url("wy", "Natrona")
        assert url is not None


# ── _pick helper ──────────────────────────────────────────────────────────────

class TestPickHelper:
    """Tests for _pick alias resolution."""

    def test_exact_match(self) -> None:
        fields = {"APN": "123456"}
        assert _pick(fields, ("APN", "PARCEL_NO")) == "123456"

    def test_second_alias(self) -> None:
        fields = {"PARCEL_NO": "789"}
        assert _pick(fields, ("APN", "PARCEL_NO")) == "789"

    def test_lowercase_fallback(self) -> None:
        fields = {"apn": "abc"}
        assert _pick(fields, ("APN",)) == "abc"

    def test_returns_none_when_no_match(self) -> None:
        fields = {"OTHER": "val"}
        assert _pick(fields, ("APN", "PARCEL_NO")) is None

    def test_skips_none_values(self) -> None:
        fields = {"APN": None, "PARCEL_NO": "FALLBACK"}
        assert _pick(fields, ("APN", "PARCEL_NO")) == "FALLBACK"


# ── Type coercion ─────────────────────────────────────────────────────────────

class TestToFloat:
    """Tests for _to_float."""

    def test_numeric(self) -> None:
        assert _to_float(42.5) == 42.5

    def test_none(self) -> None:
        assert _to_float(None) is None

    def test_non_numeric(self) -> None:
        assert _to_float("abc") is None

    def test_integer(self) -> None:
        assert _to_float(10) == 10.0


class TestToInt:
    """Tests for _to_int."""

    def test_integer(self) -> None:
        assert _to_int(100) == 100

    def test_float_string_with_commas(self) -> None:
        assert _to_int("1,250,000") == 1250000

    def test_none(self) -> None:
        assert _to_int(None) is None

    def test_non_numeric(self) -> None:
        assert _to_int("N/A") is None


# ── Normalisation ─────────────────────────────────────────────────────────────

class TestNormalise:
    """Tests for ArcGISParcelScraper._normalise."""

    def test_point_geometry(self) -> None:
        s = _scraper()
        feature = {
            "attributes": {
                "APN": "123-456-789",
                "SITUS_ADDR": "100 Main St",
                "OWNER": "John Doe",
                "TOTAL_AV": 250000,
                "ZONE_CODE": "R-1",
                "ACREAGE": 0.25,
                "LAND_USE": "SFR",
            },
            "geometry": {"x": -117.85, "y": 33.75},
        }
        result = s._normalise(feature)
        assert result["parcel_id"] == "123-456-789"
        assert result["address"] == "100 Main St"
        assert result["owner_of_record"] == "John Doe"
        assert result["assessed_total"] == 250000
        assert result["zoning"] == "R-1"
        assert result["acreage"] == 0.25
        assert result["land_use_code"] == "SFR"
        assert result["longitude"] == -117.85
        assert result["latitude"] == 33.75

    def test_polygon_geometry_centroid(self) -> None:
        """Polygon rings should produce a centroid approximation."""
        s = _scraper()
        feature = {
            "attributes": {"APN": "POLY-1"},
            "geometry": {
                "rings": [[
                    [-117.0, 33.0],
                    [-117.0, 34.0],
                    [-118.0, 34.0],
                    [-118.0, 33.0],
                    [-117.0, 33.0],
                ]]
            },
        }
        result = s._normalise(feature)
        assert result["parcel_id"] == "POLY-1"
        # Centroid of the square
        assert result["longitude"] is not None
        assert result["latitude"] is not None
        assert abs(result["longitude"] - (-117.4)) < 0.21
        assert abs(result["latitude"] - 33.6) < 0.21

    def test_no_geometry(self) -> None:
        s = _scraper()
        feature = {
            "attributes": {"APN": "NO-GEO"},
            "geometry": None,
        }
        result = s._normalise(feature)
        assert result["parcel_id"] == "NO-GEO"
        assert result["latitude"] is None
        assert result["longitude"] is None

    def test_missing_geometry_key(self) -> None:
        s = _scraper()
        feature = {"attributes": {"APN": "NO-KEY"}}
        result = s._normalise(feature)
        assert result["parcel_id"] == "NO-KEY"
        assert result["latitude"] is None

    def test_alternative_field_aliases(self) -> None:
        """Check that PARCELID, SITE_ADDRESS, etc. are resolved."""
        s = _scraper()
        feature = {
            "attributes": {
                "PARCELID": "ALT-123",
                "SITE_ADDRESS": "200 Oak Ave",
                "OWN_NAME": "Jane Smith",
                "ASSESSED_VALUE": 180000,
            },
        }
        result = s._normalise(feature)
        assert result["parcel_id"] == "ALT-123"
        assert result["address"] == "200 Oak Ave"
        assert result["owner_of_record"] == "Jane Smith"
        assert result["assessed_total"] == 180000

    def test_raw_attributes_preserved(self) -> None:
        """raw_attributes dict is included for fallback extraction."""
        s = _scraper()
        attrs = {"APN": "X", "CUSTOM_FIELD": "custom_value"}
        feature = {"attributes": attrs}
        result = s._normalise(feature)
        assert result["raw_attributes"] == attrs

    def test_empty_attributes(self) -> None:
        s = _scraper()
        feature = {"attributes": {}}
        result = s._normalise(feature)
        assert result["parcel_id"] is None
        assert result["address"] is None


# ── Query methods ─────────────────────────────────────────────────────────────

class TestQueryByApn:
    """Tests for query_by_apn with mocked HTTP."""

    @respx.mock
    async def test_found_on_first_try(self) -> None:
        s = _scraper()
        respx.get(f"{_TEST_SERVICE}/query").mock(
            return_value=httpx.Response(200, json={
                "features": [{
                    "attributes": {"APN": "123456789"},
                    "geometry": {"x": -117.0, "y": 33.0},
                }],
            })
        )
        result = await s.query_by_apn("123-456-789")
        assert result is not None
        assert result["parcel_id"] == "123456789"
        await s.close()

    @respx.mock
    async def test_not_found(self) -> None:
        s = _scraper()
        respx.get(f"{_TEST_SERVICE}/query").mock(
            return_value=httpx.Response(200, json={"features": []})
        )
        result = await s.query_by_apn("NONEXISTENT")
        assert result is None
        await s.close()

    @respx.mock
    async def test_normalises_apn_input(self) -> None:
        """Input APN with dashes/spaces is cleaned before query."""
        s = _scraper()
        route = respx.get(f"{_TEST_SERVICE}/query").mock(
            return_value=httpx.Response(200, json={"features": []})
        )
        await s.query_by_apn("12-34 56")
        # Verify the cleaned APN was used in the query
        assert route.called
        first_url = str(route.calls[0].request.url)
        assert "123456" in first_url
        await s.close()

    @respx.mock
    async def test_tries_multiple_where_clauses(self) -> None:
        """If the first WHERE doesn't match, subsequent WHEREs are tried."""
        s = _scraper()
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(200, json={"features": []})
            return httpx.Response(200, json={
                "features": [{"attributes": {"APN": "FOUND"}}],
            })

        respx.get(f"{_TEST_SERVICE}/query").mock(side_effect=handler)
        result = await s.query_by_apn("XYZ")
        assert result is not None
        assert result["parcel_id"] == "FOUND"
        assert call_count == 3
        await s.close()

    @respx.mock
    async def test_http_error_raises(self) -> None:
        s = _scraper()
        respx.get(f"{_TEST_SERVICE}/query").mock(
            return_value=httpx.Response(500, text="Server Error")
        )
        with pytest.raises(httpx.HTTPStatusError):
            await s.query_by_apn("123")
        await s.close()

    @respx.mock
    async def test_timeout_raises(self) -> None:
        s = _scraper()
        respx.get(f"{_TEST_SERVICE}/query").mock(
            side_effect=httpx.ReadTimeout("timed out")
        )
        with pytest.raises(httpx.ReadTimeout):
            await s.query_by_apn("123")
        await s.close()


class TestQueryByAddress:
    """Tests for query_by_address with mocked HTTP."""

    @respx.mock
    async def test_returns_list(self) -> None:
        s = _scraper()
        respx.get(f"{_TEST_SERVICE}/query").mock(
            return_value=httpx.Response(200, json={
                "features": [
                    {"attributes": {"APN": "A1", "SITUS_ADDR": "100 Main St"}},
                    {"attributes": {"APN": "A2", "SITUS_ADDR": "100 Main Ave"}},
                ],
            })
        )
        results = await s.query_by_address("100 Main St, Orlando")
        assert len(results) == 2
        assert results[0]["parcel_id"] == "A1"
        await s.close()

    @respx.mock
    async def test_empty_results(self) -> None:
        s = _scraper()
        respx.get(f"{_TEST_SERVICE}/query").mock(
            return_value=httpx.Response(200, json={"features": []})
        )
        results = await s.query_by_address("Nonexistent Road")
        assert results == []
        await s.close()


class TestQueryBbox:
    """Tests for query_bbox with mocked HTTP."""

    @respx.mock
    async def test_returns_parcels_in_bbox(self) -> None:
        s = _scraper()
        respx.get(f"{_TEST_SERVICE}/query").mock(
            return_value=httpx.Response(200, json={
                "features": [
                    {"attributes": {"APN": "BB1"}, "geometry": {"x": -117.0, "y": 33.0}},
                ],
            })
        )
        results = await s.query_bbox((-117.1, 32.9, -116.9, 33.1))
        assert len(results) == 1
        assert results[0]["parcel_id"] == "BB1"
        await s.close()

    @respx.mock
    async def test_sends_geometry_params(self) -> None:
        s = _scraper()
        route = respx.get(f"{_TEST_SERVICE}/query").mock(
            return_value=httpx.Response(200, json={"features": []})
        )
        await s.query_bbox((-117.0, 33.0, -116.0, 34.0), max_records=50)
        assert route.called
        url_str = str(route.calls[0].request.url)
        assert "geometry=" in url_str
        assert "esriGeometryEnvelope" in url_str
        assert "esriSpatialRelIntersects" in url_str
        await s.close()


# ── Map exporter ──────────────────────────────────────────────────────────────

_MAP_SERVICE = "https://gis.example.gov/arcgis/rest/services/Parcels/MapServer"


class TestArcGISMapExporter:
    """Tests for ArcGISMapExporter."""

    @respx.mock
    async def test_export_returns_png_bytes(self) -> None:
        exporter = ArcGISMapExporter(service_url=_MAP_SERVICE)
        # Bypass rate limiter on the internal BaseScraper
        exporter._base._rate_limiter = AsyncMock()
        exporter._base._rate_limiter.acquire = AsyncMock()

        fake_png = b"\x89PNG\r\n\x1a\nfake-image-data"
        respx.get(f"{_MAP_SERVICE}/export").mock(
            return_value=httpx.Response(200, content=fake_png)
        )
        result = await exporter.export(bbox=(-117.0, 33.0, -116.0, 34.0))
        assert result == fake_png
        await exporter.close()

    @respx.mock
    async def test_export_sends_correct_params(self) -> None:
        exporter = ArcGISMapExporter(
            service_url=_MAP_SERVICE,
            layer_ids="show:0,1,2",
        )
        exporter._base._rate_limiter = AsyncMock()
        exporter._base._rate_limiter.acquire = AsyncMock()

        route = respx.get(f"{_MAP_SERVICE}/export").mock(
            return_value=httpx.Response(200, content=b"img")
        )
        await exporter.export(
            bbox=(-117.0, 33.0, -116.0, 34.0),
            width=1024,
            height=768,
        )
        assert route.called
        url_str = str(route.calls[0].request.url)
        assert "format=png" in url_str
        assert "f=image" in url_str
        assert "1024" in url_str
        assert "768" in url_str
        assert "show%3A0%2C1%2C2" in url_str or "show:0,1,2" in url_str
        await exporter.close()

    @respx.mock
    async def test_export_http_error(self) -> None:
        exporter = ArcGISMapExporter(service_url=_MAP_SERVICE)
        exporter._base._rate_limiter = AsyncMock()
        exporter._base._rate_limiter.acquire = AsyncMock()

        respx.get(f"{_MAP_SERVICE}/export").mock(
            return_value=httpx.Response(500, text="Error")
        )
        with pytest.raises(httpx.HTTPStatusError):
            await exporter.export(bbox=(-117.0, 33.0, -116.0, 34.0))
        await exporter.close()

    @respx.mock
    async def test_export_timeout(self) -> None:
        exporter = ArcGISMapExporter(service_url=_MAP_SERVICE)
        exporter._base._rate_limiter = AsyncMock()
        exporter._base._rate_limiter.acquire = AsyncMock()

        respx.get(f"{_MAP_SERVICE}/export").mock(
            side_effect=httpx.ReadTimeout("timed out")
        )
        with pytest.raises(httpx.ReadTimeout):
            await exporter.export(bbox=(-117.0, 33.0, -116.0, 34.0))
        await exporter.close()

    def test_trailing_slash_stripped(self) -> None:
        exporter = ArcGISMapExporter(service_url=f"{_MAP_SERVICE}/")
        assert not exporter.service_url.endswith("/")

    async def test_close(self) -> None:
        exporter = ArcGISMapExporter(service_url=_MAP_SERVICE)
        await exporter.close()  # should not raise


# ── Constructor ───────────────────────────────────────────────────────────────

class TestConstructor:
    """Tests for ArcGISParcelScraper initialisation."""

    def test_trailing_slash_stripped(self) -> None:
        s = ArcGISParcelScraper(service_url=f"{_TEST_SERVICE}/")
        assert not s.service_url.endswith("/")

    def test_service_url_stored(self) -> None:
        s = ArcGISParcelScraper(service_url=_TEST_SERVICE)
        assert s.service_url == _TEST_SERVICE
