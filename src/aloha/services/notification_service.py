"""Notification service — alerts, deadline monitoring, email stubs."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from aloha.db.models.alert import Alert
from aloha.db.models.tax_lien import TaxLien
from aloha.services.base import BaseService


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

    # ── Email delivery stubs ─────────────────────────────────────────────

    async def send_scan_complete(
        self,
        user_id: str,
        state: str,
        county: str,
        count: int,
    ) -> None:
        """Send a scan-complete notification email (stub).

        In production, dispatches via SendGrid or similar.
        """
        self.log.info(
            "scan_complete_email_stub",
            user_id=user_id,
            state=state,
            county=county,
            parcels_found=count,
        )
