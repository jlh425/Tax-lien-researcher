"""CAPTCHA solver integration via the 2captcha REST API.

Supports reCAPTCHA v2/v3 and image CAPTCHAs encountered by Playwright scrapers.
All methods return ``None`` gracefully when the API key is not configured or on
any failure — callers must check the return value.

Usage::

    handler = CaptchaHandler()
    if handler.is_configured:
        token = await handler.solve_recaptcha_v2(
            site_key="6Le-...",
            page_url="https://example.gov/assessor",
        )
        if token:
            await page.evaluate(f'document.getElementById("g-recaptcha-response").value="{token}"')
"""

from __future__ import annotations

import asyncio
import base64
from typing import Any

import httpx
import structlog

log = structlog.get_logger().bind(component="captcha_handler")

_SUBMIT_URL = "https://2captcha.com/in.php"
_RESULT_URL = "https://2captcha.com/res.php"
_POLL_INTERVAL = 5  # seconds between status checks
_OK_PREFIX = "OK|"


class CaptchaHandler:
    """Wraps the 2captcha REST API for reCAPTCHA and image CAPTCHA solving.

    Args:
        api_key: 2captcha API key. Defaults to ``settings.two_captcha_api_key``.
    """

    def __init__(self, api_key: str | None = None) -> None:
        if api_key is not None:
            self._api_key: str | None = api_key
        else:
            try:
                from aloha.config import settings

                self._api_key = settings.two_captcha_api_key
            except Exception:
                self._api_key = None

    @property
    def is_configured(self) -> bool:
        """True if a 2captcha API key is set."""
        return bool(self._api_key)

    async def solve_recaptcha_v2(
        self,
        site_key: str,
        page_url: str,
        *,
        timeout: int = 120,
    ) -> str | None:
        """Submit a reCAPTCHA v2 challenge and wait for the solution token.

        Args:
            site_key: The ``data-sitekey`` attribute from the page.
            page_url: Full URL of the page containing the CAPTCHA.
            timeout: Max seconds to wait for the solver (default 120).

        Returns:
            The g-recaptcha-response token string, or ``None`` on failure.
        """
        if not self.is_configured:
            log.warning("captcha_not_configured", method="recaptcha_v2")
            return None

        captcha_id = await self._submit_recaptcha(site_key, page_url)
        if not captcha_id:
            return None
        return await self._poll_result(captcha_id, timeout=timeout)

    async def solve_recaptcha_v3(
        self,
        site_key: str,
        page_url: str,
        action: str = "verify",
        *,
        timeout: int = 120,
    ) -> str | None:
        """Submit a reCAPTCHA v3 challenge.

        Args:
            site_key: The site key.
            page_url: Full page URL.
            action: reCAPTCHA action name (default "verify").
            timeout: Max wait seconds.

        Returns:
            Token string or None.
        """
        if not self.is_configured:
            log.warning("captcha_not_configured", method="recaptcha_v3")
            return None

        captcha_id = await self._submit_recaptcha(site_key, page_url, version="v3", action=action)
        if not captcha_id:
            return None
        return await self._poll_result(captcha_id, timeout=timeout)

    async def solve_image_captcha(self, image_bytes: bytes) -> str | None:
        """Submit an image CAPTCHA and return the solved text.

        Args:
            image_bytes: Raw image bytes (PNG, JPG, GIF, BMP).

        Returns:
            Solved text string, or ``None`` on failure.
        """
        if not self.is_configured:
            log.warning("captcha_not_configured", method="image")
            return None

        encoded = base64.b64encode(image_bytes).decode()
        captcha_id = await self._submit_image(encoded)
        if not captcha_id:
            return None
        return await self._poll_result(captcha_id, timeout=60)

    # ── Internal submission helpers ───────────────────────────────────────

    async def _submit_recaptcha(
        self,
        site_key: str,
        page_url: str,
        version: str = "v2",
        action: str = "verify",
    ) -> str | None:
        """POST to 2captcha /in.php and return the captcha ID."""
        data: dict[str, Any] = {
            "key": self._api_key,
            "method": "userrecaptcha",
            "googlekey": site_key,
            "pageurl": page_url,
            "json": 0,
        }
        if version == "v3":
            data["version"] = "v3"
            data["action"] = action
            data["min_score"] = 0.3

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(_SUBMIT_URL, data=data)
                resp.raise_for_status()
                text = resp.text.strip()
        except Exception as exc:
            log.warning("captcha_submit_failed", error=str(exc))
            return None

        if text.startswith(_OK_PREFIX):
            captcha_id = text[len(_OK_PREFIX) :]
            log.debug("captcha_submitted", captcha_id=captcha_id)
            return captcha_id

        log.warning("captcha_submit_error", response=text)
        return None

    async def _submit_image(self, encoded_image: str) -> str | None:
        """POST a base64-encoded image CAPTCHA and return the captcha ID."""
        data = {
            "key": self._api_key,
            "method": "base64",
            "body": encoded_image,
            "json": 0,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(_SUBMIT_URL, data=data)
                resp.raise_for_status()
                text = resp.text.strip()
        except Exception as exc:
            log.warning("captcha_image_submit_failed", error=str(exc))
            return None

        if text.startswith(_OK_PREFIX):
            return text[len(_OK_PREFIX) :]
        log.warning("captcha_image_submit_error", response=text)
        return None

    async def _poll_result(self, captcha_id: str, *, timeout: int = 120) -> str | None:
        """Poll 2captcha /res.php until the solution is ready or timeout."""
        params = {
            "key": self._api_key,
            "action": "get",
            "id": captcha_id,
            "json": 0,
        }
        elapsed = 0
        # Initial wait before first poll
        await asyncio.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL

        while elapsed < timeout:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(_RESULT_URL, params=params)
                    resp.raise_for_status()
                    text = resp.text.strip()
            except Exception as exc:
                log.warning("captcha_poll_failed", error=str(exc))
                return None

            if text.startswith(_OK_PREFIX):
                token = text[len(_OK_PREFIX) :]
                log.debug("captcha_solved", captcha_id=captcha_id)
                return token

            if text == "CAPCHA_NOT_READY":
                await asyncio.sleep(_POLL_INTERVAL)
                elapsed += _POLL_INTERVAL
                continue

            # Any other response is an error code
            log.warning("captcha_poll_error", captcha_id=captcha_id, response=text)
            return None

        log.warning("captcha_timeout", captcha_id=captcha_id, timeout=timeout)
        return None
