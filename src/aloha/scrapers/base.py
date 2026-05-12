"""Base scraper with retry logic, rate limiting, circuit breaker, and session management."""

from __future__ import annotations

import random
import time
import threading
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from aloha.scrapers.rate_limiter import TokenBucketRateLimiter
from aloha.scrapers.stealth.helper import StealthHelper

# Module-level singletons shared across all scraper instances
_shared_rate_limiter = TokenBucketRateLimiter(rate=2.0, burst=5)
_shared_stealth = StealthHelper()

_cb_log = structlog.get_logger().bind(component="circuit_breaker")


# ── Circuit breaker ──────────────────────────────────────────────────────────


class CircuitOpenError(Exception):
    """Raised when a request is rejected because the circuit breaker is open.

    Attributes:
        domain: The domain whose circuit is open.
        retry_after: Seconds until the circuit transitions to half-open.
    """

    def __init__(self, domain: str, retry_after: float) -> None:
        self.domain = domain
        self.retry_after = retry_after
        super().__init__(
            f"Circuit open for {domain!r} — retry after {retry_after:.1f}s"
        )


class CircuitBreaker:
    """Simple circuit breaker: closed -> open -> half-open -> closed.

    Thread-safe via a lock so it can be shared across async tasks that may
    run on different threads (though typically they share one event loop).

    States:
        **closed** (normal): requests pass through.  Track consecutive failures.
        **open** (fast-fail): after ``failure_threshold`` consecutive failures,
            reject immediately for ``recovery_timeout`` seconds.
        **half-open** (probe): after the recovery timeout elapses, allow up to
            ``half_open_max`` requests.  If they succeed the circuit closes;
            if any fail the circuit re-opens.
    """

    _CLOSED = "closed"
    _OPEN = "open"
    _HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max: int = 1,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self._state: str = self._CLOSED
        self._failure_count: int = 0
        self._opened_at: float = 0.0
        self._half_open_calls: int = 0
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        """Return the current state, auto-transitioning open -> half-open."""
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    def can_execute(self) -> bool:
        """Return ``True`` if a request is allowed through the breaker."""
        with self._lock:
            self._maybe_transition_to_half_open()

            if self._state == self._CLOSED:
                return True

            if self._state == self._HALF_OPEN:
                if self._half_open_calls < self.half_open_max:
                    self._half_open_calls += 1
                    return True
                return False

            # OPEN
            return False

    def record_success(self) -> None:
        """Record a successful request — resets the breaker to closed."""
        with self._lock:
            self._failure_count = 0
            if self._state == self._HALF_OPEN:
                self._state = self._CLOSED
                self._half_open_calls = 0

    def record_failure(self) -> None:
        """Record a failed request — may trip the circuit to open."""
        with self._lock:
            self._failure_count += 1

            if self._state == self._HALF_OPEN:
                # Any failure in half-open immediately re-opens
                self._state = self._OPEN
                self._opened_at = time.monotonic()
                self._half_open_calls = 0
                return

            if (
                self._state == self._CLOSED
                and self._failure_count >= self.failure_threshold
            ):
                self._state = self._OPEN
                self._opened_at = time.monotonic()

    def time_until_half_open(self) -> float:
        """Seconds remaining before the circuit transitions to half-open.

        Returns 0.0 if the circuit is not open.
        """
        with self._lock:
            if self._state != self._OPEN:
                return 0.0
            elapsed = time.monotonic() - self._opened_at
            remaining = self.recovery_timeout - elapsed
            return max(0.0, remaining)

    # ── Internal ──────────────────────────────────────────────────────────

    def _maybe_transition_to_half_open(self) -> None:
        """Transition from open to half-open if the recovery timeout has passed.

        Must be called while holding ``self._lock``.
        """
        if self._state != self._OPEN:
            return
        elapsed = time.monotonic() - self._opened_at
        if elapsed >= self.recovery_timeout:
            self._state = self._HALF_OPEN
            self._half_open_calls = 0


# Module-level registry: domain -> CircuitBreaker instance
_circuit_breakers: dict[str, CircuitBreaker] = {}
_cb_registry_lock = threading.Lock()


def get_circuit_breaker(
    domain: str,
    *,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    half_open_max: int = 1,
) -> CircuitBreaker:
    """Return the per-domain circuit breaker, creating one if needed."""
    with _cb_registry_lock:
        if domain not in _circuit_breakers:
            _circuit_breakers[domain] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                half_open_max=half_open_max,
            )
        return _circuit_breakers[domain]


# ── Jitter helper ────────────────────────────────────────────────────────────


def _jittered_wait(base: float, *, jitter_factor: float = 0.25) -> float:
    """Apply random jitter of +/-``jitter_factor`` to a base wait time.

    Example: base=4.0, jitter_factor=0.25 -> uniform in [3.0, 5.0].
    """
    low = base * (1.0 - jitter_factor)
    high = base * (1.0 + jitter_factor)
    return random.uniform(low, high)  # noqa: S311


# ── Base scraper ─────────────────────────────────────────────────────────────


class BaseScraper(ABC):
    """Abstract scraper that every county/state scraper inherits from.

    Provides an ``httpx.AsyncClient`` session, tenacity-based retries,
    rate-limiting, and per-domain circuit breakers so subclasses only
    implement ``scrape``.
    """

    MAX_RETRIES: int = 3
    BACKOFF_MIN: float = 1.0
    BACKOFF_MAX: float = 30.0
    DEFAULT_TIMEOUT: float = 30.0

    # Circuit breaker defaults (subclasses may override)
    CB_FAILURE_THRESHOLD: int = 5
    CB_RECOVERY_TIMEOUT: float = 60.0
    CB_HALF_OPEN_MAX: int = 1

    def __init__(self, *, headers: dict[str, str] | None = None) -> None:
        self.log: structlog.stdlib.BoundLogger = structlog.get_logger().bind(
            scraper=type(self).__name__,
        )
        self._headers = headers or {
            "User-Agent": "Aloha-Research/0.1 (+https://aloha.example.com)",
        }
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter: TokenBucketRateLimiter = _shared_rate_limiter
        self._stealth: StealthHelper = _shared_stealth

    # ── Session management ────────────────────────────────────────────────

    async def get_client(self) -> httpx.AsyncClient:
        """Return (and lazily create) the shared async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self._headers,
                timeout=httpx.Timeout(self.DEFAULT_TIMEOUT),
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Gracefully close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ── Rate limiting (placeholder) ───────────────────────────────────────

    async def _respect_rate_limit(self, domain: str | None = None) -> None:
        """Consume one token from the per-domain bucket, sleeping if needed."""
        target = domain or "default"
        await self._rate_limiter.acquire(target)

    # ── Circuit breaker ───────────────────────────────────────────────────

    def _get_circuit_breaker(self, domain: str) -> CircuitBreaker:
        """Return the circuit breaker for *domain*."""
        return get_circuit_breaker(
            domain,
            failure_threshold=self.CB_FAILURE_THRESHOLD,
            recovery_timeout=self.CB_RECOVERY_TIMEOUT,
            half_open_max=self.CB_HALF_OPEN_MAX,
        )

    # ── Abstract interface ────────────────────────────────────────────────

    @abstractmethod
    async def scrape(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """Fetch and parse data from the target URL.

        Args:
            url: The endpoint to scrape.
            params: Optional query / form parameters.

        Returns:
            Parsed data structure (dict, list, etc.).
        """

    # ── Retry wrapper ─────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def _fetch(
        self,
        url: str,
        *,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Perform an HTTP request with automatic retries.

        The circuit breaker is checked **before** the request.  On success the
        breaker records a success; on failure it records a failure which may
        trip the circuit open for that domain.

        Args:
            url: Target URL.
            method: HTTP method.
            params: Query parameters.
            data: Form/body data for POST requests.

        Returns:
            The httpx Response object.

        Raises:
            CircuitOpenError: If the circuit breaker for this domain is open.
        """
        domain = urlparse(url).netloc or "default"
        cb = self._get_circuit_breaker(domain)

        # Fast-fail if the circuit is open
        if not cb.can_execute():
            retry_after = cb.time_until_half_open()
            self.log.warning(
                "circuit_open",
                domain=domain,
                retry_after=retry_after,
                hint="consider escalating to next scraper tier",
            )
            raise CircuitOpenError(domain, retry_after)

        await self._respect_rate_limit(domain)
        client = await self.get_client()
        self.log.debug("http_request", method=method, url=url)

        try:
            response = await client.request(method, url, params=params, data=data)
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.TransportError):
            cb.record_failure()
            if cb.state == CircuitBreaker._OPEN:
                self.log.warning(
                    "circuit_tripped",
                    domain=domain,
                    recovery_timeout=cb.recovery_timeout,
                    hint="consider escalating to next scraper tier",
                )
            raise

        cb.record_success()
        return response
