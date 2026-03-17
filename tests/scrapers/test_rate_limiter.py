"""Unit tests for TokenBucketRateLimiter."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from aloha.scrapers.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiter:
    """Tests for per-domain token-bucket rate limiting."""

    @pytest.mark.asyncio
    async def test_acquires_up_to_burst_immediately(self) -> None:
        """Acquiring up to the burst capacity should not sleep."""
        limiter = TokenBucketRateLimiter(rate=2.0, burst=5)
        slept: list[float] = []

        async def fake_sleep(secs: float) -> None:
            slept.append(secs)

        with patch("asyncio.sleep", side_effect=fake_sleep):
            for _ in range(5):
                await limiter.acquire("example.com")

        # No sleep should have occurred — bucket had 5 tokens
        assert slept == []

    @pytest.mark.asyncio
    async def test_throttles_beyond_burst(self) -> None:
        """The (burst+1)-th acquisition must sleep."""
        limiter = TokenBucketRateLimiter(rate=2.0, burst=3)
        slept: list[float] = []

        async def fake_sleep(secs: float) -> None:
            slept.append(secs)

        with patch("asyncio.sleep", side_effect=fake_sleep):
            for _ in range(4):  # burst=3 → 4th must sleep
                await limiter.acquire("example.com")

        assert len(slept) == 1
        assert slept[0] > 0

    @pytest.mark.asyncio
    async def test_separate_domains_are_independent(self) -> None:
        """Acquiring from domain A does not deplete domain B's bucket."""
        limiter = TokenBucketRateLimiter(rate=2.0, burst=2)
        slept: list[float] = []

        async def fake_sleep(secs: float) -> None:
            slept.append(secs)

        with patch("asyncio.sleep", side_effect=fake_sleep):
            # Drain domain A (2 tokens)
            await limiter.acquire("a.example.com")
            await limiter.acquire("a.example.com")
            # Domain B still has full bucket — should not sleep
            await limiter.acquire("b.example.com")
            await limiter.acquire("b.example.com")

        # Only domain A's 3rd+ calls would sleep; we only called A twice
        assert slept == []

    @pytest.mark.asyncio
    async def test_refill_over_time(self) -> None:
        """Tokens refill at the configured rate after time elapses."""
        limiter = TokenBucketRateLimiter(rate=1.0, burst=2)
        slept: list[float] = []

        async def fake_sleep(secs: float) -> None:
            slept.append(secs)

        # Drain the bucket
        base_time = 1_000_000.0
        with patch("time.monotonic", return_value=base_time):
            with patch("asyncio.sleep", side_effect=fake_sleep):
                await limiter.acquire("test.com")
                await limiter.acquire("test.com")

        # Simulate 2 seconds passing — should refill 2 tokens (rate=1.0)
        with patch("time.monotonic", return_value=base_time + 2.0):
            with patch("asyncio.sleep", side_effect=fake_sleep):
                # These should succeed without sleeping
                initial_sleep_count = len(slept)
                await limiter.acquire("test.com")
                await limiter.acquire("test.com")
                assert len(slept) == initial_sleep_count, "No new sleeps expected after refill"

    @pytest.mark.asyncio
    async def test_sleep_duration_proportional_to_deficit(self) -> None:
        """Sleep duration should be inversely proportional to rate."""
        # rate=1.0 means 1 token/sec → sleeping 1.0s for each missing token
        limiter = TokenBucketRateLimiter(rate=1.0, burst=1)
        slept: list[float] = []

        async def fake_sleep(secs: float) -> None:
            slept.append(secs)

        with patch("asyncio.sleep", side_effect=fake_sleep):
            await limiter.acquire("slow.com")   # consumes the 1 token
            await limiter.acquire("slow.com")   # must sleep ~1.0s

        assert len(slept) == 1
        assert abs(slept[0] - 1.0) < 0.1, f"Expected ~1.0s sleep, got {slept[0]}"

    @pytest.mark.asyncio
    async def test_default_domain_works(self) -> None:
        """Calling acquire() with no domain uses 'default' bucket."""
        limiter = TokenBucketRateLimiter(rate=10.0, burst=5)
        # Should not raise
        await limiter.acquire()

    @pytest.mark.asyncio
    async def test_burst_cap_enforced(self) -> None:
        """Tokens never exceed burst even after long elapsed time."""
        limiter = TokenBucketRateLimiter(rate=100.0, burst=3)
        slept: list[float] = []

        async def fake_sleep(secs: float) -> None:
            slept.append(secs)

        # Pre-seed with a very old timestamp to simulate lots of elapsed time
        limiter._buckets["burst.com"] = (0.0, time.monotonic() - 1000.0)

        with patch("asyncio.sleep", side_effect=fake_sleep):
            # Should be able to acquire burst=3 times without sleeping
            for _ in range(3):
                await limiter.acquire("burst.com")
            # 4th should require sleeping
            await limiter.acquire("burst.com")

        assert len(slept) == 1
