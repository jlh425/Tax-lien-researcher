"""Token-bucket rate limiter for per-domain request throttling.

Each domain gets its own bucket. Tokens refill at ``rate`` per second up to
``burst``. Callers ``await acquire(domain)`` before making a request; the call
sleeps until a token is available.
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, Tuple


class TokenBucketRateLimiter:
    """Per-domain token-bucket rate limiter.

    Args:
        rate: Tokens added per second (default 2.0 — two requests/second/domain).
        burst: Maximum tokens a bucket can hold (default 5 — short bursts OK).
    """

    def __init__(self, rate: float = 2.0, burst: int = 5) -> None:
        self.rate = rate
        self.burst = burst
        # domain -> (tokens, last_refill_ts)
        self._buckets: Dict[str, Tuple[float, float]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, domain: str) -> asyncio.Lock:
        if domain not in self._locks:
            self._locks[domain] = asyncio.Lock()
        return self._locks[domain]

    async def acquire(self, domain: str = "default") -> None:
        """Block until one token is available for *domain*."""
        lock = self._get_lock(domain)
        async with lock:
            now = time.monotonic()
            tokens, last_refill = self._buckets.get(domain, (float(self.burst), now))

            # Refill tokens based on elapsed time
            elapsed = now - last_refill
            tokens = min(float(self.burst), tokens + elapsed * self.rate)

            if tokens >= 1.0:
                # Token available — consume and return immediately
                self._buckets[domain] = (tokens - 1.0, now)
                return

            # No token — calculate wait time and sleep
            deficit = 1.0 - tokens
            wait = deficit / self.rate
            await asyncio.sleep(wait)

            # Re-timestamp after sleep
            self._buckets[domain] = (0.0, time.monotonic())
