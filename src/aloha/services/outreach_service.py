"""Outreach service — DNC checks, frequency caps, approval, template rendering."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import httpx
from jinja2 import Environment
from sqlalchemy import func, select

from aloha.core.exceptions import OutreachBlockedError
from aloha.db.models.outreach import DoNotContact, OutreachLog, OutreachTemplate
from aloha.services.base import BaseService

_SENDGRID_SEND_URL = "https://api.sendgrid.com/v3/mail/send"
_TWILIO_BASE_URL = "https://api.twilio.com/2010-04-01"
_HTTP_TIMEOUT = 15.0

_FREQUENCY_CAP_DAYS = 14


class OutreachService(BaseService):
    """Manages outreach lifecycle: DNC, frequency caps, approval, sending."""

    # ── DNC / compliance checks ──────────────────────────────────────────

    async def check_dnc(self, contact_value: str, contact_type: str) -> bool:
        """Return True if the contact is on the do-not-contact list."""
        result = await self._session.execute(
            select(func.count())
            .select_from(DoNotContact)
            .where(
                DoNotContact.contact_value == contact_value,
                DoNotContact.contact_type == contact_type,
            ),
        )
        return result.scalar_one() > 0

    async def check_frequency_cap(
        self,
        user_id: str,
        owner_id: int,
        channel: str,
    ) -> bool:
        """Return True if the owner was already contacted within the cap window."""
        cutoff = datetime.now(tz=UTC) - timedelta(days=_FREQUENCY_CAP_DAYS)
        result = await self._session.execute(
            select(func.count())
            .select_from(OutreachLog)
            .where(
                OutreachLog.owner_id == owner_id,
                OutreachLog.channel == channel,
                OutreachLog.created_at >= cutoff,
                OutreachLog.status.in_(["sent", "delivered", "opened", "replied"]),
            ),
        )
        return result.scalar_one() > 0

    # ── Outreach lifecycle ───────────────────────────────────────────────

    async def schedule_outreach(
        self,
        *,
        user_id: str,
        parcel_id: str | None,
        owner_id: int,
        channel: str,
        contact_value: str,
        template_name: str | None = None,
        variables: dict | None = None,
    ) -> int:
        """Create a pending outreach log entry after compliance checks.

        Returns the outreach log ID. Raises OutreachBlockedError if DNC or
        frequency cap blocks the attempt.
        """
        # DNC check
        contact_type = "email" if channel == "email" else "phone"
        if await self.check_dnc(contact_value, contact_type):
            raise OutreachBlockedError(
                f"Contact {contact_value!r} is on the do-not-contact list.",
            )

        # Frequency cap
        if await self.check_frequency_cap(user_id, owner_id, channel):
            raise OutreachBlockedError(
                f"Owner {owner_id} was already contacted via {channel} "
                f"within the last {_FREQUENCY_CAP_DAYS} days.",
            )

        # Render message body if template provided
        message_body = None
        subject = None
        if template_name:
            rendered = await self._render_from_db(template_name, variables or {})
            message_body = rendered.get("body")
            subject = rendered.get("subject")

        log_entry = OutreachLog(
            user_id=user_id,
            parcel_id=parcel_id,
            owner_id=owner_id,
            channel=channel,
            contact_value=contact_value,
            template_name=template_name,
            subject=subject,
            message_body=message_body,
            status="pending",
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(log_entry)
        await self._session.flush()

        self.log.info(
            "outreach_scheduled",
            outreach_id=log_entry.id,
            channel=channel,
            owner_id=owner_id,
        )
        return log_entry.id

    async def approve_outreach(self, outreach_log_id: int) -> None:
        """Mark a pending outreach entry as approved for sending."""
        entry = await self._session.get(OutreachLog, outreach_log_id)
        if entry is None:
            raise ValueError(f"OutreachLog {outreach_log_id} not found")
        entry.status = "approved"
        entry.approved_at = datetime.now(tz=UTC)
        await self._session.flush()
        self.log.info("outreach_approved", outreach_id=outreach_log_id)

    async def send_outreach(self, outreach_log_id: int) -> None:
        """Send an approved outreach message via SendGrid (email) or Twilio (SMS).

        Dispatches to the appropriate provider based on the outreach channel.
        Falls back to stub mode if API keys are not configured.
        """
        entry = await self._session.get(OutreachLog, outreach_log_id)
        if entry is None:
            raise ValueError(f"OutreachLog {outreach_log_id} not found")
        if entry.status != "approved":
            raise ValueError(
                f"OutreachLog {outreach_log_id} is not approved (status={entry.status})"
            )

        from aloha.config import settings

        if entry.channel == "email":
            provider_msg_id = await self._send_email(
                settings=settings,
                to_email=entry.contact_value,
                subject=entry.subject or "(No subject)",
                body=entry.message_body or "",
            )
            entry.provider = "sendgrid"
        elif entry.channel in ("sms", "voicemail"):
            provider_msg_id = await self._send_sms(
                settings=settings,
                to_phone=entry.contact_value,
                body=entry.message_body or "",
            )
            entry.provider = "twilio"
        else:
            # Unsupported channel — mark as stub
            self.log.warning("unsupported_channel", channel=entry.channel)
            provider_msg_id = f"stub_{outreach_log_id}"
            entry.provider = "stub"

        entry.status = "sent"
        entry.sent_at = datetime.now(tz=UTC)
        entry.provider_msg_id = provider_msg_id
        await self._session.flush()

        self.log.info(
            "outreach_sent",
            outreach_id=outreach_log_id,
            channel=entry.channel,
            provider=entry.provider,
        )

    # ── Provider dispatch ─────────────────────────────────────────────

    async def _send_email(
        self,
        *,
        settings: object,
        to_email: str,
        subject: str,
        body: str,
    ) -> str:
        """Send an email via the SendGrid v3 Mail Send API.

        Returns the provider message ID. Falls back to stub if API key
        is not configured.
        """
        api_key = getattr(settings, "sendgrid_api_key", None)
        if not api_key:
            self.log.warning("sendgrid_not_configured, using stub")
            return "stub_no_sendgrid_key"

        from_email = getattr(settings, "sendgrid_from_email", "noreply@aloha-research.com")
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_email},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(_HTTP_TIMEOUT)) as client:
            response = await client.post(
                _SENDGRID_SEND_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()

        # SendGrid returns the message ID in the X-Message-Id header
        msg_id = response.headers.get("X-Message-Id", "")
        self.log.info("email_sent", to=to_email, message_id=msg_id)
        return msg_id

    async def _send_sms(
        self,
        *,
        settings: object,
        to_phone: str,
        body: str,
    ) -> str:
        """Send an SMS via the Twilio REST API.

        Returns the provider message SID. Falls back to stub if
        credentials are not configured.
        """
        account_sid = getattr(settings, "twilio_account_sid", None)
        auth_token = getattr(settings, "twilio_auth_token", None)
        from_phone = getattr(settings, "twilio_phone_number", None)

        if not all([account_sid, auth_token, from_phone]):
            self.log.warning("twilio_not_configured, using stub")
            return "stub_no_twilio_creds"

        url = f"{_TWILIO_BASE_URL}/Accounts/{account_sid}/Messages.json"
        auth = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()

        async with httpx.AsyncClient(timeout=httpx.Timeout(_HTTP_TIMEOUT)) as client:
            response = await client.post(
                url,
                data={"To": to_phone, "From": from_phone, "Body": body},
                headers={"Authorization": f"Basic {auth}"},
            )
            response.raise_for_status()

        result = response.json()
        sid = result.get("sid", "")
        self.log.info("sms_sent", to=to_phone, sid=sid)
        return sid

    # ── Template rendering ───────────────────────────────────────────────

    @staticmethod
    def render_template(template_body: str, variables: dict) -> str:
        """Render a Jinja2 template string with the provided variables."""
        env = Environment(autoescape=False)
        tpl = env.from_string(template_body)
        return tpl.render(**variables)

    async def _render_from_db(
        self,
        template_name: str,
        variables: dict,
    ) -> dict[str, str | None]:
        """Load a template by name from the DB and render it."""
        result = await self._session.execute(
            select(OutreachTemplate).where(
                OutreachTemplate.template_name == template_name,
                OutreachTemplate.is_active.is_(True),
            ),
        )
        tpl = result.scalars().first()
        if tpl is None:
            self.log.warning("template_not_found", template_name=template_name)
            return {"subject": None, "body": None}

        body = self.render_template(tpl.body, variables) if tpl.body else None
        subject = self.render_template(tpl.subject, variables) if tpl.subject else None
        return {"subject": subject, "body": body}
