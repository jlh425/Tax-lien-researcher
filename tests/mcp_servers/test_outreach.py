"""Tests for the Outreach MCP Server."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aloha.mcp_servers.outreach.server import (
    OutreachMCPServer,
    create_outreach_server,
)


def _server() -> OutreachMCPServer:
    return OutreachMCPServer(
        sendgrid_api_key="sg-key",
        twilio_account_sid="AC123",
        twilio_auth_token="tw-token",
        twilio_phone_number="+15005550006",
    )


# -- Init & Tool Registration -------------------------------------------------

class TestInit:
    def test_server_name(self) -> None:
        assert _server().name == "outreach"

    def test_tools_registered(self) -> None:
        server = _server()
        assert "send_email" in server.tools
        assert "send_sms" in server.tools
        assert "check_delivery_status" in server.tools

    def test_tool_count(self) -> None:
        assert len(_server().tools) == 3

    def test_clients_initially_none(self) -> None:
        server = _server()
        assert server._sg_client is None
        assert server._tw_client is None


# -- Success Paths (mocked HTTP) -----------------------------------------------

class TestSuccessPaths:
    @pytest.mark.asyncio
    async def test_send_email_success(self) -> None:
        server = _server()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"x-message-id": "msg-abc123"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        server._sg_client = mock_client

        result = await server.send_email(
            to_email="user@example.com",
            from_email="noreply@aloha.com",
            subject="Test",
            body="Hello",
        )
        assert result["success"] is True
        assert result["message_id"] == "msg-abc123"

    @pytest.mark.asyncio
    async def test_send_email_with_html(self) -> None:
        server = _server()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"x-message-id": "msg-html"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        server._sg_client = mock_client

        result = await server.send_email(
            to_email="user@example.com",
            from_email="noreply@aloha.com",
            subject="Test",
            body="Hello",
            html_body="<b>Hello</b>",
        )
        assert result["success"] is True
        # Verify the payload included HTML content
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        content_types = [c["type"] for c in payload["content"]]
        assert "text/html" in content_types

    @pytest.mark.asyncio
    async def test_send_sms_success(self) -> None:
        server = _server()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "sid": "SM_abc123",
            "status": "queued",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        server._tw_client = mock_client

        result = await server.send_sms(to_phone="+14155551234", message="Hello")
        assert result["success"] is True
        assert result["message_sid"] == "SM_abc123"
        assert result["status"] == "queued"

    @pytest.mark.asyncio
    async def test_check_delivery_status_sms(self) -> None:
        server = _server()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "sid": "SM_abc123",
            "status": "delivered",
            "to": "+14155551234",
            "from": "+15005550006",
            "date_sent": "2024-01-15T10:30:00Z",
            "error_code": None,
            "error_message": None,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        server._tw_client = mock_client

        result = await server.check_delivery_status("SM_abc123", "sms")
        assert result["status"] == "delivered"
        assert result["message_sid"] == "SM_abc123"

    @pytest.mark.asyncio
    async def test_check_delivery_status_email_returns_note(self) -> None:
        server = _server()
        result = await server.check_delivery_status("msg-123", "email")
        assert "note" in result
        assert "webhook" in result["note"].lower()

    @pytest.mark.asyncio
    async def test_check_delivery_status_unknown_channel(self) -> None:
        server = _server()
        result = await server.check_delivery_status("msg-123", "fax")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_close_cleans_up_both_clients(self) -> None:
        server = _server()
        sg = AsyncMock()
        sg.is_closed = False
        sg.aclose = AsyncMock()
        tw = AsyncMock()
        tw.is_closed = False
        tw.aclose = AsyncMock()
        server._sg_client = sg
        server._tw_client = tw

        await server.close()
        sg.aclose.assert_awaited_once()
        tw.aclose.assert_awaited_once()
        assert server._sg_client is None
        assert server._tw_client is None


# -- Error Paths ---------------------------------------------------------------

class TestErrorPaths:
    @pytest.mark.asyncio
    async def test_send_email_http_error(self) -> None:
        server = _server()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        error = httpx.HTTPStatusError("Bad", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=error)
        mock_client.is_closed = False
        server._sg_client = mock_client

        result = await server.send_email(
            to_email="x@x.com", from_email="y@y.com", subject="S", body="B"
        )
        assert "error" in result
        assert "400" in result["error"]

    @pytest.mark.asyncio
    async def test_send_sms_http_error(self) -> None:
        server = _server()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        error = httpx.HTTPStatusError("Unauth", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=error)
        mock_client.is_closed = False
        server._tw_client = mock_client

        result = await server.send_sms("+1234", "hi")
        assert "error" in result
        assert "401" in result["error"]

    @pytest.mark.asyncio
    async def test_send_sms_generic_exception(self) -> None:
        server = _server()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("network down"))
        mock_client.is_closed = False
        server._tw_client = mock_client

        result = await server.send_sms("+1234", "hi")
        assert "error" in result
        assert "network down" in result["error"]

    @pytest.mark.asyncio
    async def test_check_twilio_status_error(self) -> None:
        server = _server()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=error)
        mock_client.is_closed = False
        server._tw_client = mock_client

        result = await server.check_delivery_status("SM_bad", "sms")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_unknown_tool_raises_key_error(self) -> None:
        server = _server()
        with pytest.raises(KeyError):
            await server.handle_call("missing", {})


# -- Factory -------------------------------------------------------------------

class TestFactory:
    def test_create_outreach_server_missing_all(self) -> None:
        with patch("aloha.config.settings") as mock_settings:
            mock_settings.sendgrid_api_key = None
            mock_settings.twilio_account_sid = None
            mock_settings.twilio_auth_token = None
            mock_settings.twilio_phone_number = None
            with pytest.raises(ValueError, match="SENDGRID_API_KEY"):
                create_outreach_server()

    def test_create_outreach_server_missing_twilio(self) -> None:
        with patch("aloha.config.settings") as mock_settings:
            mock_settings.sendgrid_api_key = "sg-key"
            mock_settings.twilio_account_sid = None
            mock_settings.twilio_auth_token = "token"
            mock_settings.twilio_phone_number = "+1555"
            with pytest.raises(ValueError, match="TWILIO_ACCOUNT_SID"):
                create_outreach_server()

    def test_create_outreach_server_success(self) -> None:
        with patch("aloha.config.settings") as mock_settings:
            mock_settings.sendgrid_api_key = "sg-key"
            mock_settings.twilio_account_sid = "AC123"
            mock_settings.twilio_auth_token = "token"
            mock_settings.twilio_phone_number = "+15005550006"
            server = create_outreach_server()
            assert isinstance(server, OutreachMCPServer)
            assert server._sg_api_key == "sg-key"
