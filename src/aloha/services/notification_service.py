"""Notification service — alerts, deadline monitoring, email delivery."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from aloha.db.models.alert import Alert
from aloha.db.models.tax_lien import TaxLien
from aloha.services.base import BaseService

_SENDGRID_SEND_URL = "https://api.sendgrid.com/v3/mail/send"
_HTTP_TIMEOUT = 15.0


class NotificationService(BaseService):
    """Alert creation, deadline monitoring, and delivery stubs."""

    # ── Alert creation ───────────────────────────────────────────────────

    async def create_alert(
        self,
        *,
        parcel_id: str | None = None,
        alert_type: str,
        message: str | None = None,
        alert_date: date | None = None,
    ) -> int:
        """Create a new alert record and return its ID."""
        alert = Alert(
            parcel_id=parcel_id,
            alert_type=alert_type,
            message=message,
            alert_date=alert_date,
            sent=False,
            created_at=datetime.now(tz=timezone.utc),
        )
        self._session.add(alert)
        await self._session.flush()
        self.log.info("alert_created", alert_id=alert.id, alert_type=alert_type)
        return alert.id

    # ── Deadline monitoring ──────────────────────────────────────────────

    async def check_deadline_alerts(self, days_ahead: int = 30) -> list[Alert]:
        """Find liens with approaching deadlines and create alerts.

        Checks both redemption deadlines and auction dates within the
        specified window. Returns newly created alert records.
        """
        cutoff = date.today() + timedelta(days=days_ahead)
        now = date.today()

        # Redemption deadlines
        redemption_result = await self._session.execute(
            select(TaxLien).where(
                TaxLien.redemption_deadline.isnot(None),
                TaxLien.redemption_deadline >= now,
                TaxLien.redemption_deadline <= cutoff,
                TaxLien.lien_status == "active",
            ),
        )
        redemption_liens = redemption_result.scalars().all()

        # Auction dates
        auction_result = await self._session.execute(
            select(TaxLien).where(
                TaxLien.auction_date.isnot(None),
                TaxLien.auction_date >= now,
                TaxLien.auction_date <= cutoff,
            ),
        )
        auction_liens = auction_result.scalars().all()

        created_alerts: list[Alert] = []

        for lien in redemption_liens:
            days_left = (lien.redemption_deadline - now).days
            alert_id = await self.create_alert(
                parcel_id=lien.parcel_id,
                alert_type="redemption_deadline",
                message=(
                    f"Redemption deadline in {days_left} days "
                    f"({lien.redemption_deadline.isoformat()}) — "
                    f"cert #{lien.certificate_number or 'N/A'}"
                ),
                alert_date=lien.redemption_deadline,
            )
            alert = await self._session.get(Alert, alert_id)
            if alert:
                created_alerts.append(alert)

        for lien in auction_liens:
            days_left = (lien.auction_date - now).days
            alert_id = await self.create_alert(
                parcel_id=lien.parcel_id,
                alert_type="auction_date",
                message=(
                    f"Auction in {days_left} days "
                    f"({lien.auction_date.isoformat()}) — "
                    f"{lien.auction_platform or 'unknown platform'}"
                ),
                alert_date=lien.auction_date,
            )
            alert = await self._session.get(Alert, alert_id)
            if alert:
                created_alerts.append(alert)

        self.log.info(
            "deadline_check_complete",
            redemption_count=len(redemption_liens),
            auction_count=len(auction_liens),
            alerts_created=len(created_alerts),
        )
        return created_alerts

    # ── Email delivery ───────────────────────────────────────────────────

    async def send_scan_complete(
        self,
        user_id: str,
        state: str,
        county: str,
        count: int,
    ) -> None:
        """Send a scan-complete notification email via SendGrid.

        Falls back to log-only if SendGrid API key is not configured.
        """
        from aloha.config import settings

        api_key = settings.sendgrid_api_key
        if not api_key:
            self.log.info(
                "scan_complete_email_stub",
                user_id=user_id,
                state=state,
                county=county,
                parcels_found=count,
            )
            return

        from_email = settings.sendgrid_from_email
        subject = f"Scan complete: {county.title()} County, {state.upper()}"
        body = (
            f"Your tax lien scan for {county.title()} County, {state.upper()} "
            f"is complete.\n\n"
            f"Parcels found: {count}\n\n"
            f"Log in to your dashboard to view results."
        )

        # Look up user email — for now we embed user_id as the recipient.
        # A production setup would query the users table for the email.
        to_email = user_id  # Assumes user_id is an email or resolved upstream

        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_email},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }

        try:
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

            msg_id = response.headers.get("X-Message-Id", "")
            self.log.info(
                "scan_complete_email_sent",
                user_id=user_id,
                message_id=msg_id,
                state=state,
                county=county,
                parcels_found=count,
            )
        except Exception as exc:
            self.log.warning(
                "scan_complete_email_failed",
                user_id=user_id,
                error=str(exc),
            )
