"""Unit tests for CaptchaHandler (2captcha REST API integration).

All tests mock httpx to avoid real network calls.
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from aloha.scrapers.captcha.handler import CaptchaHandler


class TestCaptchaHandlerConfiguration:
    """Tests for handler configuration and is_configured property."""

    def test_returns_false_when_no_api_key(self) -> None:
        handler = CaptchaHandler(api_key=None)
        assert handler.is_configured is False

    def test_returns_true_when_api_key_provided(self) -> None:
        handler = CaptchaHandler(api_key="abc123")
        assert handler.is_configured is True

    @pytest.mark.asyncio
    async def test_solve_recaptcha_returns_none_when_not_configured(self) -> None:
        handler = CaptchaHandler(api_key=None)
        result = await handler.solve_recaptcha_v2(
            site_key="6Le-fake",
            page_url="https://example.gov/assessor",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_solve_image_returns_none_when_not_configured(self) -> None:
        handler = CaptchaHandler(api_key=None)
        result = await handler.solve_image_captcha(b"fake-image-bytes")
        assert result is None


class TestRecaptchaV2Solving:
    """Tests for solve_recaptcha_v2 with mocked HTTP."""

    def _make_response(self, text: str, status_code: int = 200) -> MagicMock:
        resp = MagicMock(spec=httpx.Response)
        resp.text = text
        resp.status_code = status_code
        resp.raise_for_status = MagicMock()
        return resp

    @pytest.mark.asyncio
    async def test_success_flow(self) -> None:
        """Submit returns captcha ID; poll returns token."""
        handler = CaptchaHandler(api_key="test-key")

        submit_response = self._make_response("OK|CAPTCHA_12345")
        poll_response = self._make_response("OK|MY_SOLUTION_TOKEN")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=submit_response)
        mock_client.get = AsyncMock(return_value=poll_response)

        with patch("aloha.scrapers.captcha.handler.asyncio.sleep", new_callable=AsyncMock):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await handler.solve_recaptcha_v2(
                    site_key="6Le-test",
                    page_url="https://example.com",
                    timeout=30,
                )

        assert result == "MY_SOLUTION_TOKEN"

    @pytest.mark.asyncio
    async def test_submit_error_returns_none(self) -> None:
        """If the submit call returns an error code, return None."""
        handler = CaptchaHandler(api_key="test-key")
        error_response = self._make_response("ERROR_ZERO_BALANCE")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=error_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await handler.solve_recaptcha_v2(
                site_key="6Le-test",
                page_url="https://example.com",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_poll_not_ready_then_success(self) -> None:
        """Polling returns CAPCHA_NOT_READY first, then the token."""
        handler = CaptchaHandler(api_key="test-key")

        submit_response = self._make_response("OK|ID_999")
        not_ready = self._make_response("CAPCHA_NOT_READY")
        success = self._make_response("OK|FINAL_TOKEN")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=submit_response)
        mock_client.get = AsyncMock(side_effect=[not_ready, success])

        with patch("aloha.scrapers.captcha.handler.asyncio.sleep", new_callable=AsyncMock):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await handler.solve_recaptcha_v2(
                    site_key="6Le-test",
                    page_url="https://example.com",
                    timeout=60,
                )

        assert result == "FINAL_TOKEN"

    @pytest.mark.asyncio
    async def test_poll_timeout_returns_none(self) -> None:
        """If all polls return CAPCHA_NOT_READY within timeout, return None."""
        handler = CaptchaHandler(api_key="test-key")

        submit_response = self._make_response("OK|ID_TIMEOUT")
        not_ready = self._make_response("CAPCHA_NOT_READY")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=submit_response)
        # Always return not_ready
        mock_client.get = AsyncMock(return_value=not_ready)

        sleep_count = [0]

        async def fake_sleep(secs: float) -> None:
            sleep_count[0] += 1
            if sleep_count[0] > 5:
                # Force timeout by resetting elapsed counter artificially
                raise StopAsyncIteration

        with patch("aloha.scrapers.captcha.handler.asyncio.sleep", side_effect=fake_sleep):
            with patch("httpx.AsyncClient", return_value=mock_client):
                # Use a very short timeout so the while loop terminates
                handler_result = await handler._poll_result("ID_TIMEOUT", timeout=0)

        assert handler_result is None

    @pytest.mark.asyncio
    async def test_poll_error_code_returns_none(self) -> None:
        """A non-OK, non-READY poll response returns None immediately."""
        handler = CaptchaHandler(api_key="test-key")

        submit_response = self._make_response("OK|ID_ERR")
        error_response = self._make_response("ERROR_WRONG_CAPTCHA_ID")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=submit_response)
        mock_client.get = AsyncMock(return_value=error_response)

        with patch("aloha.scrapers.captcha.handler.asyncio.sleep", new_callable=AsyncMock):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await handler.solve_recaptcha_v2(
                    site_key="6Le-test",
                    page_url="https://example.com",
                    timeout=30,
                )

        assert result is None


class TestImageCaptcha:
    """Tests for solve_image_captcha."""

    @pytest.mark.asyncio
    async def test_image_bytes_are_base64_encoded_in_post(self) -> None:
        """POST body must contain base64-encoded image."""
        handler = CaptchaHandler(api_key="test-key")
        image_bytes = b"fake-png-data"
        expected_b64 = base64.b64encode(image_bytes).decode()

        captured_data: list[dict] = []

        def _make_response(text: str) -> MagicMock:
            resp = MagicMock(spec=httpx.Response)
            resp.text = text
            resp.raise_for_status = MagicMock()
            return resp

        async def fake_post(url: str, data: dict | None = None, **kwargs) -> MagicMock:
            if data:
                captured_data.append(dict(data))
            return _make_response("OK|IMG_ID")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=fake_post)
        mock_client.get = AsyncMock(return_value=_make_response("OK|SOLVED_TEXT"))

        with patch("aloha.scrapers.captcha.handler.asyncio.sleep", new_callable=AsyncMock):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await handler.solve_image_captcha(image_bytes)

        assert result == "SOLVED_TEXT"
        assert len(captured_data) == 1
        assert captured_data[0]["body"] == expected_b64
        assert captured_data[0]["method"] == "base64"
