"""Unit tests for CircuitBreaker — state transitions, per-domain isolation,
BaseScraper integration, and jitter.

All tests use respx to mock httpx calls; no real network traffic.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from aloha.scrapers.base import (
    BaseScraper,
    CircuitBreaker,
    CircuitOpenError,
    _circuit_breakers,
    _jittered_wait,
    get_circuit_breaker,
)


# ── Concrete subclass for testing ────────────────────────────────────────────


class _StubScraper(BaseScraper):
    """Minimal concrete implementation so we can test the base class."""

    async def scrape(self, url: str, params: dict[str, Any] | None = None) -> Any:
        resp = await self._fetch(url, params=params)
        return resp.json()


def _stub(*, headers: dict[str, str] | None = None) -> _StubScraper:
    scraper = _StubScraper(headers=headers)
    # Bypass rate limiter for most tests so they run fast
    scraper._rate_limiter = AsyncMock()
    scraper._rate_limiter.acquire = AsyncMock()
    return scraper


# ── State transitions ────────────────────────────────────────────────────────


class TestCircuitBreakerStateTransitions:
    """Tests for closed -> open -> half-open -> closed state machine."""

    def test_starts_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == "closed"

    def test_stays_closed_below_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"

    def test_opens_after_failure_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        base_time = time.monotonic()
        with patch("time.monotonic", return_value=base_time):
            for _ in range(3):
                cb.record_failure()
        # Check state within recovery window
        with patch("time.monotonic", return_value=base_time + 1.0):
            assert cb.state == "open"

    def test_open_rejects_immediately(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)
        base_time = time.monotonic()
        with patch("time.monotonic", return_value=base_time):
            cb.record_failure()
            cb.record_failure()
        with patch("time.monotonic", return_value=base_time + 1.0):
            assert cb.state == "open"
            assert cb.can_execute() is False

    def test_half_open_after_recovery_timeout(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=10.0)
        base_time = time.monotonic()

        with patch("time.monotonic", return_value=base_time):
            cb.record_failure()
            cb.record_failure()

        # Still within recovery window — should be open
        with patch("time.monotonic", return_value=base_time + 5.0):
            assert cb.state == "open"

        # Simulate time passing beyond recovery timeout
        with patch("time.monotonic", return_value=base_time + 11.0):
            assert cb.state == "half_open"

    def test_half_open_allows_limited_requests(self) -> None:
        cb = CircuitBreaker(
            failure_threshold=2, recovery_timeout=5.0, half_open_max=1,
        )
        base_time = 1_000_000.0

        with patch("time.monotonic", return_value=base_time):
            cb.record_failure()
            cb.record_failure()

        with patch("time.monotonic", return_value=base_time + 6.0):
            # First call should be allowed (half-open probe)
            assert cb.can_execute() is True
            # Second call should be rejected (half_open_max=1)
            assert cb.can_execute() is False

    def test_half_open_success_closes_circuit(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=5.0)
        base_time = 1_000_000.0

        with patch("time.monotonic", return_value=base_time):
            cb.record_failure()
            cb.record_failure()

        with patch("time.monotonic", return_value=base_time + 6.0):
            assert cb.state == "half_open"
            cb.can_execute()  # consume the half-open slot
            cb.record_success()
            assert cb.state == "closed"

    def test_half_open_failure_reopens_circuit(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=5.0)
        base_time = time.monotonic()

        with patch("time.monotonic", return_value=base_time):
            cb.record_failure()
            cb.record_failure()

        with patch("time.monotonic", return_value=base_time + 6.0):
            assert cb.state == "half_open"
            cb.can_execute()  # consume the half-open slot
            cb.record_failure()

        # Should be open again with a new recovery timer — check within window
        with patch("time.monotonic", return_value=base_time + 7.0):
            assert cb.state == "open"

    def test_success_resets_failure_count(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()  # resets counter
        cb.record_failure()
        # Only 1 failure since reset — should still be closed
        assert cb.state == "closed"

    def test_time_until_half_open_returns_remaining(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=30.0)
        base_time = 1_000_000.0

        with patch("time.monotonic", return_value=base_time):
            cb.record_failure()

        with patch("time.monotonic", return_value=base_time + 10.0):
            remaining = cb.time_until_half_open()
            assert 19.0 <= remaining <= 21.0  # ~20s remaining

    def test_time_until_half_open_zero_when_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=5)
        assert cb.time_until_half_open() == 0.0

    def test_time_until_half_open_zero_when_half_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=5.0)
        base_time = 1_000_000.0

        with patch("time.monotonic", return_value=base_time):
            cb.record_failure()

        with patch("time.monotonic", return_value=base_time + 6.0):
            # Should have transitioned to half_open
            assert cb.state == "half_open"
            assert cb.time_until_half_open() == 0.0

    def test_can_execute_true_when_closed(self) -> None:
        cb = CircuitBreaker()
        assert cb.can_execute() is True

    def test_half_open_max_greater_than_one(self) -> None:
        cb = CircuitBreaker(
            failure_threshold=1, recovery_timeout=5.0, half_open_max=3,
        )
        base_time = 1_000_000.0

        with patch("time.monotonic", return_value=base_time):
            cb.record_failure()

        with patch("time.monotonic", return_value=base_time + 6.0):
            assert cb.can_execute() is True
            assert cb.can_execute() is True
            assert cb.can_execute() is True
            assert cb.can_execute() is False  # exceeded half_open_max


# ── Per-domain isolation ─────────────────────────────────────────────────────


class TestPerDomainIsolation:
    """Circuit breaker for domain A should not affect domain B."""

    def test_separate_domains_independent(self) -> None:
        cb_a = get_circuit_breaker(
            "a.example.com", failure_threshold=2, recovery_timeout=60.0,
        )
        cb_b = get_circuit_breaker(
            "b.example.com", failure_threshold=2, recovery_timeout=60.0,
        )
        base_time = time.monotonic()

        # Trip domain A
        with patch("time.monotonic", return_value=base_time):
            cb_a.record_failure()
            cb_a.record_failure()

        with patch("time.monotonic", return_value=base_time + 1.0):
            assert cb_a.state == "open"

            # Domain B should be unaffected
            assert cb_b.state == "closed"
            assert cb_b.can_execute() is True

    def test_get_circuit_breaker_returns_same_instance(self) -> None:
        cb1 = get_circuit_breaker("test.example.com")
        cb2 = get_circuit_breaker("test.example.com")
        assert cb1 is cb2

    def test_get_circuit_breaker_different_domains_different_instances(self) -> None:
        cb1 = get_circuit_breaker("a.example.com")
        cb2 = get_circuit_breaker("b.example.com")
        assert cb1 is not cb2


# ── CircuitOpenError ─────────────────────────────────────────────────────────


class TestCircuitOpenError:
    """Tests for the CircuitOpenError exception."""

    def test_error_attributes(self) -> None:
        err = CircuitOpenError("api.county.gov", 42.5)
        assert err.domain == "api.county.gov"
        assert err.retry_after == 42.5
        assert "api.county.gov" in str(err)
        assert "42.5" in str(err)

    def test_is_exception(self) -> None:
        err = CircuitOpenError("test", 10.0)
        assert isinstance(err, Exception)


# ── Integration with BaseScraper ─────────────────────────────────────────────


class TestBaseScraperCircuitBreakerIntegration:
    """Verify that BaseScraper._fetch checks the circuit breaker."""

    @respx.mock
    async def test_circuit_breaker_checked_before_http_call(self) -> None:
        """When circuit is open, _fetch raises CircuitOpenError without HTTP."""
        scraper = _stub()
        scraper.CB_RECOVERY_TIMEOUT = 300.0  # long timeout so it stays open
        domain = "api.example.com"
        cb = scraper._get_circuit_breaker(domain)

        # Trip the circuit
        for _ in range(5):
            cb.record_failure()
        assert cb.state == "open"

        route = respx.get(f"https://{domain}/data").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        with pytest.raises(CircuitOpenError) as exc_info:
            await scraper._fetch(f"https://{domain}/data")

        assert exc_info.value.domain == domain
        # HTTP call should NOT have been made
        assert route.call_count == 0
        await scraper.close()

    @respx.mock
    async def test_success_recorded_after_http_success(self) -> None:
        """Successful HTTP call records a success on the breaker."""
        scraper = _stub()
        domain = "api.example.com"

        respx.get(f"https://{domain}/data").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        await scraper._fetch(f"https://{domain}/data")

        cb = scraper._get_circuit_breaker(domain)
        # After success, failure count should be 0
        assert cb._failure_count == 0
        assert cb.state == "closed"
        await scraper.close()

    @respx.mock
    async def test_failure_recorded_after_http_error(self) -> None:
        """HTTP error records a failure on the breaker."""
        scraper = _stub()
        # Use a high failure threshold so the circuit doesn't trip on retries
        scraper.CB_FAILURE_THRESHOLD = 100
        domain = "api.example.com"

        respx.get(f"https://{domain}/fail").mock(
            return_value=httpx.Response(500, text="Server Error")
        )

        with pytest.raises(httpx.HTTPStatusError):
            await scraper._fetch(f"https://{domain}/fail")

        cb = scraper._get_circuit_breaker(domain)
        # tenacity retries 3 times, each records a failure
        assert cb._failure_count == 3
        await scraper.close()

    @respx.mock
    async def test_circuit_trips_during_retries(self) -> None:
        """If failures during retries trip the circuit, subsequent calls fast-fail."""
        scraper = _stub()
        scraper.CB_FAILURE_THRESHOLD = 3  # trips after 3 failures (= 1 retry cycle)
        domain = "api.example.com"

        respx.get(f"https://{domain}/fail").mock(
            return_value=httpx.Response(500, text="Server Error")
        )

        # First call: 3 retries trip the circuit
        with pytest.raises(httpx.HTTPStatusError):
            await scraper._fetch(f"https://{domain}/fail")

        cb = scraper._get_circuit_breaker(domain)
        assert cb.state == "open"

        # Second call: should fast-fail with CircuitOpenError
        with pytest.raises(CircuitOpenError):
            await scraper._fetch(f"https://{domain}/fail")

        await scraper.close()

    @respx.mock
    async def test_transport_error_records_failure(self) -> None:
        """Transport errors (timeouts) also record failures on the breaker."""
        scraper = _stub()
        scraper.CB_FAILURE_THRESHOLD = 100
        domain = "api.example.com"

        respx.get(f"https://{domain}/timeout").mock(
            side_effect=httpx.ConnectTimeout("Connection timed out")
        )

        with pytest.raises(httpx.ConnectTimeout):
            await scraper._fetch(f"https://{domain}/timeout")

        cb = scraper._get_circuit_breaker(domain)
        assert cb._failure_count == 3  # 3 retries
        await scraper.close()

    @respx.mock
    async def test_circuit_open_error_not_retried(self) -> None:
        """CircuitOpenError is NOT retried by tenacity — it fast-fails."""
        scraper = _stub()
        scraper.CB_RECOVERY_TIMEOUT = 300.0  # long timeout so it stays open
        domain = "api2.example.com"  # unique domain for this test
        cb = scraper._get_circuit_breaker(domain)

        for _ in range(5):
            cb.record_failure()

        route = respx.get(f"https://{domain}/data").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        with pytest.raises(CircuitOpenError):
            await scraper._fetch(f"https://{domain}/data")

        # Should have raised immediately without any HTTP calls
        assert route.call_count == 0
        await scraper.close()

    @respx.mock
    async def test_scraper_subclass_cb_overrides(self) -> None:
        """Subclass can override CB_FAILURE_THRESHOLD.

        With threshold=2, the first two retries record failures and trip the
        circuit. The third retry attempt sees the open circuit and raises
        CircuitOpenError (which tenacity does NOT retry since it only
        retries HTTPStatusError / TransportError).
        """

        class _CustomScraper(BaseScraper):
            CB_FAILURE_THRESHOLD = 2

            async def scrape(
                self, url: str, params: dict[str, Any] | None = None,
            ) -> Any:
                resp = await self._fetch(url, params=params)
                return resp.json()

        scraper = _CustomScraper()
        scraper._rate_limiter = AsyncMock()
        scraper._rate_limiter.acquire = AsyncMock()
        domain = "custom.example.com"

        respx.get(f"https://{domain}/fail").mock(
            return_value=httpx.Response(500, text="Error")
        )

        # Threshold=2: after 2 failures circuit opens, 3rd retry fast-fails
        with pytest.raises(CircuitOpenError):
            await scraper._fetch(f"https://{domain}/fail")

        cb = scraper._get_circuit_breaker(domain)
        assert cb.state == "open"
        await scraper.close()


# ── Jitter ───────────────────────────────────────────────────────────────────


class TestJitter:
    """Tests for the _jittered_wait helper."""

    def test_jitter_within_bounds(self) -> None:
        """Jittered values should be within +/-25% of the base."""
        base = 10.0
        for _ in range(200):
            result = _jittered_wait(base, jitter_factor=0.25)
            assert 7.5 <= result <= 12.5

    def test_jitter_produces_variation(self) -> None:
        """Multiple calls should not all return the same value."""
        base = 10.0
        values = {_jittered_wait(base) for _ in range(50)}
        # With 50 samples from a continuous uniform distribution,
        # we should see many distinct values
        assert len(values) > 5

    def test_jitter_zero_factor(self) -> None:
        """With jitter_factor=0, the result is exactly the base."""
        assert _jittered_wait(5.0, jitter_factor=0.0) == 5.0

    def test_jitter_small_base(self) -> None:
        """Jitter works correctly with very small base values."""
        for _ in range(100):
            result = _jittered_wait(0.1, jitter_factor=0.25)
            assert 0.075 <= result <= 0.125
