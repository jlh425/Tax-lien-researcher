"""Unit tests for BaseScraper — session management, retry, and rate limiting.

All tests use respx to mock httpx calls; no real network traffic.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from aloha.scrapers.base import BaseScraper


# ── Concrete subclass for testing ─────────────────────────────────────────────

class _StubScraper(BaseScraper):
    """Minimal concrete implementation so we can test the base class."""

    async def scrape(self, url: str, params: dict[str, Any] | None = None) -> Any:
        resp = await self._fetch(url, params=params)
        return resp.json()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stub(*, headers: dict[str, str] | None = None) -> _StubScraper:
    scraper = _StubScraper(headers=headers)
    # Bypass rate limiter for most tests so they run fast
    scraper._rate_limiter = AsyncMock()
    scraper._rate_limiter.acquire = AsyncMock()
    return scraper


# ── Session management ────────────────────────────────────────────────────────

class TestSessionManagement:
    """Tests for lazy client creation and cleanup."""

    async def test_get_client_creates_client(self) -> None:
        scraper = _stub()
        assert scraper._client is None
        client = await scraper.get_client()
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        await scraper.close()

    async def test_get_client_reuses_existing(self) -> None:
        scraper = _stub()
        c1 = await scraper.get_client()
        c2 = await scraper.get_client()
        assert c1 is c2
        await scraper.close()

    async def test_close_sets_client_to_none(self) -> None:
        scraper = _stub()
        await scraper.get_client()
        await scraper.close()
        assert scraper._client is None

    async def test_close_on_already_closed_is_safe(self) -> None:
        scraper = _stub()
        await scraper.close()  # no client yet — should not raise
        await scraper.get_client()
        await scraper.close()
        await scraper.close()  # double close — should not raise

    async def test_get_client_recreates_after_close(self) -> None:
        scraper = _stub()
        c1 = await scraper.get_client()
        await scraper.close()
        c2 = await scraper.get_client()
        assert c1 is not c2
        await scraper.close()

    async def test_custom_headers_applied(self) -> None:
        scraper = _stub(headers={"X-Custom": "test-value"})
        client = await scraper.get_client()
        assert client.headers.get("X-Custom") == "test-value"
        await scraper.close()

    async def test_default_user_agent(self) -> None:
        scraper = _stub()
        client = await scraper.get_client()
        assert "Aloha-Research" in client.headers.get("User-Agent", "")
        await scraper.close()


# ── Fetch and retry ───────────────────────────────────────────────────────────

class TestFetchAndRetry:
    """Tests for _fetch with mocked HTTP responses."""

    @respx.mock
    async def test_successful_get(self) -> None:
        scraper = _stub()
        route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = await scraper.scrape("https://api.example.com/data")
        assert result == {"ok": True}
        assert route.called
        await scraper.close()

    @respx.mock
    async def test_successful_post(self) -> None:
        scraper = _stub()
        route = respx.post("https://api.example.com/submit").mock(
            return_value=httpx.Response(200, json={"created": True})
        )
        resp = await scraper._fetch(
            "https://api.example.com/submit", method="POST", data={"key": "val"}
        )
        assert resp.status_code == 200
        assert route.called
        await scraper.close()

    @respx.mock
    async def test_query_params_forwarded(self) -> None:
        scraper = _stub()
        route = respx.get("https://api.example.com/search").mock(
            return_value=httpx.Response(200, json=[])
        )
        await scraper.scrape("https://api.example.com/search", params={"q": "test"})
        assert route.called
        await scraper.close()

    @respx.mock
    async def test_http_500_raises_after_retries(self) -> None:
        """Server error triggers retries then re-raises."""
        scraper = _stub()
        route = respx.get("https://api.example.com/fail").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        with pytest.raises(httpx.HTTPStatusError):
            await scraper._fetch("https://api.example.com/fail")
        # tenacity retries 3 times
        assert route.call_count == 3
        await scraper.close()

    @respx.mock
    async def test_http_404_raises_after_retries(self) -> None:
        """Client 4xx also triggers retries via HTTPStatusError."""
        scraper = _stub()
        route = respx.get("https://api.example.com/missing").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        with pytest.raises(httpx.HTTPStatusError):
            await scraper._fetch("https://api.example.com/missing")
        assert route.call_count == 3
        await scraper.close()

    @respx.mock
    async def test_http_429_raises_after_retries(self) -> None:
        """Rate limit 429 triggers retries."""
        scraper = _stub()
        route = respx.get("https://api.example.com/limited").mock(
            return_value=httpx.Response(429, text="Too Many Requests")
        )
        with pytest.raises(httpx.HTTPStatusError):
            await scraper._fetch("https://api.example.com/limited")
        assert route.call_count == 3
        await scraper.close()

    @respx.mock
    async def test_network_timeout_raises_after_retries(self) -> None:
        """Transport errors (timeout, connection reset) also trigger retries."""
        scraper = _stub()
        route = respx.get("https://api.example.com/timeout").mock(
            side_effect=httpx.ConnectTimeout("Connection timed out")
        )
        with pytest.raises(httpx.ConnectTimeout):
            await scraper._fetch("https://api.example.com/timeout")
        assert route.call_count == 3
        await scraper.close()

    @respx.mock
    async def test_transient_failure_then_success(self) -> None:
        """First request fails, retry succeeds."""
        scraper = _stub()
        route = respx.get("https://api.example.com/flaky").mock(
            side_effect=[
                httpx.Response(503, text="Unavailable"),
                httpx.Response(200, json={"recovered": True}),
            ]
        )
        resp = await scraper._fetch("https://api.example.com/flaky")
        assert resp.status_code == 200
        assert route.call_count == 2
        await scraper.close()


# ── Rate limiting integration ─────────────────────────────────────────────────

class TestRateLimitingIntegration:
    """Verify that _fetch calls the rate limiter before making requests."""

    @respx.mock
    async def test_rate_limiter_called_with_domain(self) -> None:
        scraper = _StubScraper()
        mock_limiter = AsyncMock()
        mock_limiter.acquire = AsyncMock()
        scraper._rate_limiter = mock_limiter

        respx.get("https://data.example.com/api").mock(
            return_value=httpx.Response(200, json={})
        )
        await scraper._fetch("https://data.example.com/api")
        mock_limiter.acquire.assert_called_once_with("data.example.com")
        await scraper.close()

    async def test_rate_limiter_uses_default_for_empty_netloc(self) -> None:
        """When urlparse yields empty netloc, domain falls back to 'default'."""
        from urllib.parse import urlparse
        # Verify our assumption: file:// URLs have empty netloc
        assert urlparse("file:///local/path").netloc == ""
        # We just test the _respect_rate_limit path directly
        scraper = _StubScraper()
        mock_limiter = AsyncMock()
        mock_limiter.acquire = AsyncMock()
        scraper._rate_limiter = mock_limiter
        await scraper._respect_rate_limit(domain=None)
        mock_limiter.acquire.assert_called_once_with("default")
