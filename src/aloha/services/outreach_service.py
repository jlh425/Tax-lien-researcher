"""Outreach service — DNC checks, frequency caps, approval, template rendering."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jinja2 import Environment
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aloha.core.exceptions import OutreachBlockedError
from aloha.db.models.outreach import DoNotContact, OutreachLog, OutreachTemplate
from aloha.services.base import BaseService

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
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=_FREQUENCY_CAP_DAYS)
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
            created_at=datetime.now(tz=timezone.utc),
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
        entry.approved_at = datetime.now(tz=timezone.utc)
        await self._session.flush()
        self.log.info("outreach_approved", outreach_id=outreach_log_id)

    async def send_outreach(self, outreach_log_id: int) -> None:
        """Send an approved outreach message (SendGrid/Twilio stub).

        In production, this dispatches to the appropriate provider based on
        the outreach channel. Currently logs the attempt as a stub.
        """
        entry = await self._session.get(OutreachLog, outreach_log_id)
        if entry is None:
            raise ValueError(f"OutreachLog {outreach_log_id} not found")
        if entry.status != "approved":
            raise ValueError(f"OutreachLog {outreach_log_id} is not approved (status={entry.status})")

        # Stub: mark as sent
        entry.status = "sent"
        entry.sent_at = datetime.now(tz=timezone.utc)
        entry.provider = "stub"
        entry.provider_msg_id = f"stub_{outreach_log_id}"
        await self._session.flush()

        self.log.info(
            "outreach_sent_stub",
            outreach_id=outreach_log_id,
            channel=entry.channel,
        )

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
