"""Unit tests for AdaptiveBrowserScraper (Tier 3).

All tests mock Playwright and the LLM — no real browser or network calls.
"""

from __future__ import annotations

from typing import Any

import pytest

from aloha.scrapers.tier3_adaptive.scraper import AdaptiveBrowserScraper, PagePlan


class TestPagePlanModel:
    """Tests for the PagePlan Pydantic model."""

    def test_valid_plan_constructs(self) -> None:
        plan = PagePlan(
            search_input_selector='input[name="apn"]',
            submit_selector='button[type="submit"]',
            result_table_selector="table#results",
            field_map={"parcel_id": "APN", "address": "Address"},
            confidence=0.85,
        )
        assert plan.confidence == 0.85
        assert plan.notes == ""

    def test_plan_with_zero_confidence(self) -> None:
        plan = PagePlan(
            search_input_selector="",
            submit_selector="",
            result_table_selector="",
            field_map={},
            confidence=0.0,
            notes="LLM unavailable",
        )
        assert plan.confidence == 0.0


class TestCountyUrlResolverStaticRegistry:
    """Tests for CountyUrlResolver static registry lookups (replaces _guess_assessor_url)."""

    def test_resolves_known_county_from_registry(self) -> None:
        from aloha.services.county_url_resolver import CountyUrlResolver

        resolver = CountyUrlResolver()
        url = resolver._check_static_registry("FL", "orange", "assessor")
        assert url is not None
        assert url.startswith("https://")

    def test_returns_none_for_unknown_county(self) -> None:
        from aloha.services.county_url_resolver import CountyUrlResolver

        resolver = CountyUrlResolver()
        url = resolver._check_static_registry("XX", "nonexistent", "assessor")
        assert url is None

    def test_texas_harris(self) -> None:
        from aloha.services.county_url_resolver import CountyUrlResolver

        resolver = CountyUrlResolver()
        url = resolver._check_static_registry("TX", "harris", "assessor")
        assert url == "https://hcad.org"


class TestNormaliseAdaptive:
    """Tests for AdaptiveBrowserScraper._normalise_adaptive."""

    def _scraper(self) -> AdaptiveBrowserScraper:
        s = AdaptiveBrowserScraper.__new__(AdaptiveBrowserScraper)
        s._stealth = None  # type: ignore[assignment]
        s._model = None
        return s

    def test_extracts_parcel_id_and_address(self) -> None:
        scraper = self._scraper()
        raw = {
            "parcel_id": "12-34-567-890",
            "address": "123 Main St",
            "owner": "John Doe",
        }
        result = scraper._normalise_adaptive(raw, "FL", "orange")
        assert result is not None
        assert result["parcel_id"] == "12-34-567-890"
        assert result["address"] == "123 Main St"
        assert result["state"] == "FL"
        assert result["county"] == "orange"

    def test_returns_none_without_parcel_id(self) -> None:
        scraper = self._scraper()
        raw = {"address": "123 Main St", "owner": "Jane Smith"}
        result = scraper._normalise_adaptive(raw, "FL", "orange")
        assert result is None

    def test_normalises_parcel_id_to_uppercase(self) -> None:
        scraper = self._scraper()
        raw = {"parcel_id": "ab-12-cdef"}
        result = scraper._normalise_adaptive(raw, "GA", "fulton")
        assert result is not None
        assert result["parcel_id"] == "AB-12-CDEF"

    def test_picks_apn_alias(self) -> None:
        scraper = self._scraper()
        raw = {"apn": "9876543", "col_1": "Some Street"}
        result = scraper._normalise_adaptive(raw, "CA", "los-angeles")
        assert result is not None
        assert result["parcel_id"] == "9876543"

    def test_infers_parcel_from_column_pattern(self) -> None:
        """Even with no named key, a column that looks like an APN is used."""
        scraper = self._scraper()
        raw = {"col_0": "12345678", "col_1": "456 Oak Ave"}
        result = scraper._normalise_adaptive(raw, "TX", "harris")
        assert result is not None
        assert result["parcel_id"] == "12345678"

    def test_assessed_total_parsed_as_float(self) -> None:
        scraper = self._scraper()
        raw = {"parcel_id": "ABC123", "assessed_value": "$125,000"}
        result = scraper._normalise_adaptive(raw, "FL", "orange")
        assert result is not None
        assert result["assessed_total"] == 125000.0


class TestLowConfidencePlanSkip:
    """Tests that low-confidence LLM plans abort gracefully."""

    @pytest.mark.asyncio
    async def test_low_confidence_returns_empty_list(self) -> None:
        """discover() should return [] without executing the search."""
        scraper = AdaptiveBrowserScraper()

        low_confidence_plan = PagePlan(
            search_input_selector="input",
            submit_selector="button",
            result_table_selector="table",
            field_map={},
            confidence=0.1,
            notes="Test: low confidence",
        )

        # Patch _analyse_page to return a low-confidence plan
        async def mock_analyse(page: Any, state: str, county: str) -> PagePlan:
            return low_confidence_plan

        # Patch playwright so no real browser is launched
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_browser = AsyncMock()
        mock_browser.close = AsyncMock()
        mock_playwright_ctx = AsyncMock()
        mock_playwright_ctx.chromium = MagicMock()
        mock_playwright_ctx.chromium.launch = AsyncMock(return_value=mock_browser)

        # Patch stealth helper to return the mock context
        scraper._stealth = MagicMock()
        scraper._stealth.new_context = AsyncMock(return_value=mock_context)
        scraper._analyse_page = mock_analyse  # type: ignore[method-assign]

        mock_page.goto = AsyncMock()

        # Patch at the source module where async_playwright is imported from
        with patch(
            "playwright.async_api.async_playwright",
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=mock_playwright_ctx),
                __aexit__=AsyncMock(return_value=False),
            ),
        ):
            try:
                result = await scraper.discover(
                    "https://example.gov",
                    state="XX",
                    county="test",
                )
            except ImportError:
                pytest.skip("playwright not installed in this environment")

        assert result == []


class TestPickAlias:
    """Tests for AdaptiveBrowserScraper._pick_alias static method."""

    def test_exact_match(self) -> None:
        raw = {"parcel_id": "123", "address": "456 St"}
        result = AdaptiveBrowserScraper._pick_alias(raw, ("parcel_id", "apn"))
        assert result == "123"

    def test_case_insensitive_match(self) -> None:
        raw = {"APN": "987654", "Address": "789 Ave"}
        result = AdaptiveBrowserScraper._pick_alias(raw, ("apn", "parcel_id"))
        assert result == "987654"

    def test_returns_none_when_no_match(self) -> None:
        raw = {"col_0": "value", "col_1": "other"}
        result = AdaptiveBrowserScraper._pick_alias(raw, ("parcel_id", "apn", "folio"))
        assert result is None

    def test_space_normalised_to_underscore(self) -> None:
        raw = {"parcel id": "AB123"}
        result = AdaptiveBrowserScraper._pick_alias(raw, ("parcel_id",))
        assert result == "AB123"
