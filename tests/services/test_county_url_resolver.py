"""Tests for the CountyUrlResolver service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aloha.services.county_url_resolver import CountyUrlResolver


@pytest.fixture
def resolver() -> CountyUrlResolver:
    return CountyUrlResolver()


class TestStaticRegistry:
    @pytest.mark.asyncio
    async def test_resolves_known_county(self, resolver: CountyUrlResolver) -> None:
        """Layer 2: resolves from the static registry when DB has no result."""
        with patch.object(resolver, "_check_database", return_value=None):
            with patch.object(resolver, "_persist_url", new_callable=AsyncMock):
                url = await resolver.resolve("WY", "natrona", "assessor")

        assert url == "https://assessorsearch.natronacounty-wy.gov"

    @pytest.mark.asyncio
    async def test_resolves_florida_orange(self, resolver: CountyUrlResolver) -> None:
        with patch.object(resolver, "_check_database", return_value=None):
            with patch.object(resolver, "_persist_url", new_callable=AsyncMock):
                url = await resolver.resolve("FL", "orange", "assessor")

        assert url == "https://www.ocpafl.org"


class TestDatabaseCache:
    @pytest.mark.asyncio
    async def test_returns_cached_url(self, resolver: CountyUrlResolver) -> None:
        """Layer 1: returns DB-cached URL without hitting other layers."""
        with patch.object(
            resolver, "_check_database", return_value="https://cached.example.gov"
        ):
            url = await resolver.resolve("XX", "unknown", "assessor")

        assert url == "https://cached.example.gov"


class TestWebSearch:
    @pytest.mark.asyncio
    async def test_falls_through_to_search(self, resolver: CountyUrlResolver) -> None:
        """Layers 3+4: calls web search when DB and registry miss."""
        with (
            patch.object(resolver, "_check_database", return_value=None),
            patch.object(
                resolver, "_search_web", return_value=["https://found.gov/tax"]
            ) as mock_search,
            patch.object(
                resolver, "_validate_candidates", return_value="https://found.gov/tax"
            ),
            patch.object(resolver, "_persist_url", new_callable=AsyncMock),
        ):
            url = await resolver.resolve("XX", "unknown", "assessor")

        assert url == "https://found.gov/tax"
        mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_unvalidated_if_llm_fails(
        self, resolver: CountyUrlResolver
    ) -> None:
        """Falls back to best unvalidated candidate if LLM returns None."""
        with (
            patch.object(resolver, "_check_database", return_value=None),
            patch.object(
                resolver, "_search_web", return_value=["https://best.gov/assessor"]
            ),
            patch.object(resolver, "_validate_candidates", return_value=None),
            patch.object(resolver, "_persist_url", new_callable=AsyncMock) as mock_persist,
        ):
            url = await resolver.resolve("XX", "unknown", "assessor")

        assert url == "https://best.gov/assessor"
        # Should be persisted with lower confidence
        mock_persist.assert_called_once()
        call_kwargs = mock_persist.call_args[1]
        assert call_kwargs["confidence"] == 0.5
        assert call_kwargs["source"] == "searxng"


class TestAllLayersFail:
    @pytest.mark.asyncio
    async def test_returns_none(self, resolver: CountyUrlResolver) -> None:
        """Returns None when all 4 layers fail."""
        with (
            patch.object(resolver, "_check_database", return_value=None),
            patch.object(resolver, "_search_web", return_value=[]),
        ):
            url = await resolver.resolve("XX", "nonexistent", "assessor")

        assert url is None


class TestIsLikelyTaxUrl:
    def test_gov_with_tax_keyword(self, resolver: CountyUrlResolver) -> None:
        assert resolver._is_likely_tax_url(
            "https://tax.orange.gov/property", "orange"
        )

    def test_gov_with_county_name(self, resolver: CountyUrlResolver) -> None:
        assert resolver._is_likely_tax_url(
            "https://www.orangecounty.gov/assessor", "orange"
        )

    def test_non_gov_with_both(self, resolver: CountyUrlResolver) -> None:
        assert resolver._is_likely_tax_url(
            "https://orangecounty-tax.com/property", "orange"
        )

    def test_unrelated_url(self, resolver: CountyUrlResolver) -> None:
        assert not resolver._is_likely_tax_url(
            "https://www.wikipedia.org/wiki/Orange", "orange"
        )
