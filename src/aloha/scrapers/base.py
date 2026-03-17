"""Base scraper with retry logic, rate limiting, and session management."""

from __future__ import annotations

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


class BaseScraper(ABC):
    """Abstract scraper that every county/state scraper inherits from.

    Provides an ``httpx.AsyncClient`` session, tenacity-based retries, and a
    rate-limiting placeholder so subclasses only implement ``scrape``.
    """

    MAX_RETRIES: int = 3
    BACKOFF_MIN: float = 1.0
    BACKOFF_MAX: float = 30.0
    DEFAULT_TIMEOUT: float = 30.0

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

        Args:
            url: Target URL.
            method: HTTP method.
            params: Query parameters.
            data: Form/body data for POST requests.

        Returns:
            The httpx Response object.
        """
        domain = urlparse(url).netloc or "default"
        await self._respect_rate_limit(domain)
        client = await self.get_client()
        self.log.debug("http_request", method=method, url=url)

        response = await client.request(method, url, params=params, data=data)
        response.raise_for_status()
        return response
