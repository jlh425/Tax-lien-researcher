"""Outreach MCP Server — SendGrid email + Twilio SMS.

Dual-client server: one httpx client for SendGrid (Bearer auth) and another
for Twilio (Basic auth with account SID + auth token).

Tools exposed:
- send_email: send an email via SendGrid
- send_sms: send an SMS via Twilio
- check_delivery_status: check message delivery status
"""

from __future__ import annotations

import base64
from typing import Any

import httpx
import structlog

from aloha.mcp_servers.base import BaseMCPServer, ToolDefinition

log = structlog.get_logger().bind(component="outreach_mcp")

_SENDGRID_BASE_URL = "https://api.sendgrid.com"
_TWILIO_BASE_URL = "https://api.twilio.com/2010-04-01"
_TIMEOUT = 20.0


class OutreachMCPServer(BaseMCPServer):
    """MCP server for email (SendGrid) and SMS (Twilio) outreach."""

    def __init__(
        self,
        sendgrid_api_key: str,
        twilio_account_sid: str,
        twilio_auth_token: str,
        twilio_phone_number: str,
    ) -> None:
        super().__init__(name="outreach")
        self._sg_api_key = sendgrid_api_key
        self._tw_sid = twilio_account_sid
        self._tw_token = twilio_auth_token
        self._tw_phone = twilio_phone_number
        self._sg_client: httpx.AsyncClient | None = None
        self._tw_client: httpx.AsyncClient | None = None
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(ToolDefinition(
            name="send_email",
            description=(
                "Send an email via SendGrid. Returns the message ID on success."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "to_email": {
                        "type": "string",
                        "description": "Recipient email address.",
                    },
                    "from_email": {
                        "type": "string",
                        "description": "Sender email address.",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line.",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body (plain text).",
                    },
                    "html_body": {
                        "type": "string",
                        "description": "Optional HTML body.",
                    },
                },
                "required": ["to_email", "from_email", "subject", "body"],
            },
            handler=self.send_email,
        ))

        self.register_tool(ToolDefinition(
            name="send_sms",
            description=(
                "Send an SMS message via Twilio. Returns the message SID on success."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "to_phone": {
                        "type": "string",
                        "description": "Recipient phone number in E.164 format.",
                    },
                    "message": {
                        "type": "string",
                        "description": "SMS message body (max 1600 chars).",
                    },
                },
                "required": ["to_phone", "message"],
            },
            handler=self.send_sms,
        ))

        self.register_tool(ToolDefinition(
            name="check_delivery_status",
            description=(
                "Check the delivery status of a sent message. For Twilio SMS, "
                "provide the message SID. SendGrid delivery tracking requires webhooks."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Twilio message SID or SendGrid message ID.",
                    },
                    "channel": {
                        "type": "string",
                        "description": "Delivery channel: 'sms' or 'email'.",
                    },
                },
                "required": ["message_id", "channel"],
            },
            handler=self.check_delivery_status,
        ))

    # -- HTTP clients ----------------------------------------------------------

    async def _get_sg_client(self) -> httpx.AsyncClient:
        if self._sg_client is None or self._sg_client.is_closed:
            self._sg_client = httpx.AsyncClient(
                base_url=_SENDGRID_BASE_URL,
                headers={
                    "Authorization": f"Bearer {self._sg_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(_TIMEOUT),
            )
        return self._sg_client

    async def _get_tw_client(self) -> httpx.AsyncClient:
        if self._tw_client is None or self._tw_client.is_closed:
            credentials = base64.b64encode(
                f"{self._tw_sid}:{self._tw_token}".encode()
            ).decode()
            self._tw_client = httpx.AsyncClient(
                base_url=_TWILIO_BASE_URL,
                headers={"Authorization": f"Basic {credentials}"},
                timeout=httpx.Timeout(_TIMEOUT),
            )
        return self._tw_client

    async def close(self) -> None:
        for client in (self._sg_client, self._tw_client):
            if client and not client.is_closed:
                await client.aclose()
        self._sg_client = None
        self._tw_client = None

    # -- Tool handlers ---------------------------------------------------------

    async def send_email(
        self,
        to_email: str,
        from_email: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> dict[str, Any]:
        """Send an email via SendGrid v3 API."""
        content = [{"type": "text/plain", "value": body}]
        if html_body:
            content.append({"type": "text/html", "value": html_body})

        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_email},
            "subject": subject,
            "content": content,
        }

        try:
            client = await self._get_sg_client()
            response = await client.post("/v3/mail/send", json=payload)
            response.raise_for_status()
            message_id = response.headers.get("x-message-id", "")
            log.info("email_sent", to=to_email, message_id=message_id)
            return {"success": True, "message_id": message_id}
        except httpx.HTTPStatusError as exc:
            body_text = exc.response.text
            log.warning("sendgrid_error", status=exc.response.status_code, body=body_text)
            return {"error": f"SendGrid error {exc.response.status_code}: {body_text}"}
        except Exception as exc:
            log.error("email_send_failed", error=str(exc))
            return {"error": str(exc)}

    async def send_sms(
        self,
        to_phone: str,
        message: str,
    ) -> dict[str, Any]:
        """Send an SMS via Twilio."""
        try:
            client = await self._get_tw_client()
            response = await client.post(
                f"/Accounts/{self._tw_sid}/Messages.json",
                data={
                    "To": to_phone,
                    "From": self._tw_phone,
                    "Body": message,
                },
            )
            response.raise_for_status()
            data = response.json()
            sid = data.get("sid", "")
            log.info("sms_sent", to=to_phone, sid=sid)
            return {"success": True, "message_sid": sid, "status": data.get("status")}
        except httpx.HTTPStatusError as exc:
            log.warning("twilio_error", status=exc.response.status_code)
            return {"error": f"Twilio error {exc.response.status_code}"}
        except Exception as exc:
            log.error("sms_send_failed", error=str(exc))
            return {"error": str(exc)}

    async def check_delivery_status(
        self,
        message_id: str,
        channel: str,
    ) -> dict[str, Any]:
        """Check delivery status of a sent message."""
        if channel == "sms":
            return await self._check_twilio_status(message_id)
        if channel == "email":
            return {
                "message_id": message_id,
                "note": "SendGrid delivery tracking requires webhook configuration. "
                        "Check SendGrid Activity Feed for real-time status.",
            }
        return {"error": f"Unknown channel: {channel!r}. Use 'sms' or 'email'."}

    async def _check_twilio_status(self, message_sid: str) -> dict[str, Any]:
        """Fetch Twilio message status."""
        try:
            client = await self._get_tw_client()
            response = await client.get(
                f"/Accounts/{self._tw_sid}/Messages/{message_sid}.json",
            )
            response.raise_for_status()
            data = response.json()
            return {
                "message_sid": data.get("sid"),
                "status": data.get("status"),
                "to": data.get("to"),
                "from": data.get("from"),
                "date_sent": data.get("date_sent"),
                "error_code": data.get("error_code"),
                "error_message": data.get("error_message"),
            }
        except httpx.HTTPStatusError as exc:
            log.warning("twilio_status_error", status=exc.response.status_code)
            return {"error": f"Twilio error {exc.response.status_code}"}
        except Exception as exc:
            log.error("twilio_status_failed", error=str(exc))
            return {"error": str(exc)}


# -- Factory -------------------------------------------------------------------

def create_outreach_server() -> OutreachMCPServer:
    """Build the Outreach MCP server from settings.

    Raises:
        ValueError: If any required SendGrid or Twilio credentials are missing.
    """
    from aloha.config import settings

    missing = []
    if not settings.sendgrid_api_key:
        missing.append("SENDGRID_API_KEY")
    if not settings.twilio_account_sid:
        missing.append("TWILIO_ACCOUNT_SID")
    if not settings.twilio_auth_token:
        missing.append("TWILIO_AUTH_TOKEN")
    if not settings.twilio_phone_number:
        missing.append("TWILIO_PHONE_NUMBER")
    if missing:
        raise ValueError(
            f"{', '.join(missing)} required to use the Outreach MCP server."
        )
    return OutreachMCPServer(
        sendgrid_api_key=settings.sendgrid_api_key,
        twilio_account_sid=settings.twilio_account_sid,
        twilio_auth_token=settings.twilio_auth_token,
        twilio_phone_number=settings.twilio_phone_number,
    )
