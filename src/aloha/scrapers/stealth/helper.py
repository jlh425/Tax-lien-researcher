"""Stealth browser helper for Playwright scrapers.

Provides randomised User-Agent strings, viewport sizes, and human-like
inter-action delays to reduce bot-detection rates on county assessor portals.
Optionally applies ``playwright-stealth`` JS evasions if the package is installed.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

import structlog

log = structlog.get_logger().bind(component="stealth_helper")

# ---------------------------------------------------------------------------
# Fallback User-Agent pool (used when fake-useragent is unavailable or fails)
# ---------------------------------------------------------------------------
_FALLBACK_UAS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

# Common desktop viewport sizes
_VIEWPORTS: list[dict[str, int]] = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 800},
    {"width": 1536, "height": 864},
    {"width": 1600, "height": 900},
]


class StealthHelper:
    """Provides randomised Playwright context options and human-like delays.

    Args:
        min_delay: Minimum seconds to sleep for human_delay (default 0.5).
        max_delay: Maximum seconds to sleep for human_delay (default 2.5).
    """

    def __init__(self, min_delay: float = 0.5, max_delay: float = 2.5) -> None:
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._ua_generator: Any = None
        self._ua_initialized = False

    def _get_ua_generator(self) -> Any:
        if self._ua_initialized:
            return self._ua_generator
        self._ua_initialized = True
        try:
            from fake_useragent import UserAgent  # type: ignore[import]
            self._ua_generator = UserAgent()
        except Exception:
            log.debug("fake_useragent_unavailable", fallback="using hardcoded UA list")
            self._ua_generator = None
        return self._ua_generator

    def random_user_agent(self) -> str:
        """Return a random desktop User-Agent string."""
        ua_gen = self._get_ua_generator()
        if ua_gen is not None:
            try:
                return ua_gen.chrome  # type: ignore[no-any-return]
            except Exception as e:
                log.debug("ua_generator_failed", error=str(e))
        return random.choice(_FALLBACK_UAS)

    def random_viewport(self) -> dict[str, int]:
        """Return a random common desktop viewport."""
        return random.choice(_VIEWPORTS)

    async def new_context(self, browser: Any) -> Any:
        """Create a Playwright browser context with stealth settings.

        Args:
            browser: A ``playwright.async_api.Browser`` instance.

        Returns:
            A ``BrowserContext`` with randomised UA, viewport, and optional
            JS evasions via ``playwright-stealth``.
        """
        context = await browser.new_context(
            user_agent=self.random_user_agent(),
            viewport=self.random_viewport(),
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            },
            java_script_enabled=True,
            ignore_https_errors=True,
        )

        # Apply playwright-stealth JS evasions if available (optional dependency)
        try:
            from playwright_stealth import stealth_async  # type: ignore[import]
            # stealth_async works on pages, not contexts; apply per-page via route
            # Store flag so new_page callers can apply it
            context._stealth_enabled = True  # type: ignore[attr-defined]
        except ImportError:
            context._stealth_enabled = False  # type: ignore[attr-defined]

        return context

    async def human_delay(self) -> None:
        """Sleep for a random human-like duration."""
        await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))
