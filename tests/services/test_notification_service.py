"""Comprehensive tests for the NotificationService.

Covers create_alert edge cases, check_deadline_alerts with redemption
and auction deadlines, and send_scan_complete variants.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aloha.services.notification_service import NotificationService


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_service(session: AsyncMock | None = None) -> tuple[NotificationService, AsyncMock]:
    """Instantiate NotificationService with a mocked session."""
    session = session or AsyncMock()
    # session.add is synchronous in SQLAlchemy
    session.add = MagicMock()
    svc = NotificationService(session)
    return svc, session


def _make_lien(
    *,
    parcel_id: str = "P001",
    redemption_deadline: date | None = None,
    auction_date: date | None = None,
    lien_status: str = "active",
    certificate_number: str | None = "CERT-001",
    auction_platform: str | None = None,
) -> MagicMock:
    """Build a mock TaxLien with deadline fields."""
    lien = MagicMock()
    lien.parcel_id = parcel_id
    lien.redemption_deadline = redemption_deadline
    lien.auction_date = auction_date
    lien.lien_status = lien_status
    lien.certificate_number = certificate_number
    lien.auction_platform = auction_platform
    return lien


# ═══════════════════════════════════════════════════════════════════════════════
# create_alert
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateAlert:
    """Tests for create_alert beyond the basic test in test_services.py."""

    @pytest.mark.asyncio
    async def test_create_alert_without_optional_fields(self) -> None:
        """create_alert works with only alert_type (no parcel_id, message, date)."""
        svc, session = _make_service()
        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def fake_flush():
            if added_objects:
                added_objects[-1].id = 1

        session.flush.side_effect = fake_flush

        alert_id = await svc.create_alert(alert_type="new_high_score")
        assert alert_id == 1
        obj = added_objects[0]
        assert obj.parcel_id is None
        assert obj.message is None
        assert obj.alert_date is None
        assert obj.alert_type == "new_high_score"

    @pytest.mark.asyncio
    async def test_create_alert_sets_sent_false(self) -> None:
        """create_alert always sets sent=False initially."""
        svc, session = _make_service()
        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def fake_flush():
            if added_objects:
                added_objects[-1].id = 10

        session.flush.side_effect = fake_flush

        await svc.create_alert(
            parcel_id="P001",
            alert_type="lien_status_change",
            message="Status changed to redeemed",
        )
        obj = added_objects[0]
        assert obj.sent is False

    @pytest.mark.asyncio
    async def test_create_alert_sets_created_at(self) -> None:
        """create_alert sets created_at to a UTC timestamp."""
        svc, session = _make_service()
        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def fake_flush():
            if added_objects:
                added_objects[-1].id = 11

        session.flush.side_effect = fake_flush

        before = datetime.now(tz=timezone.utc)
        await svc.create_alert(alert_type="test_type")
        after = datetime.now(tz=timezone.utc)

        obj = added_objects[0]
        assert before <= obj.created_at <= after

    @pytest.mark.asyncio
    async def test_create_alert_db_error_propagates(self) -> None:
        """create_alert propagates DB flush errors."""
        svc, session = _make_service()
        session.flush.side_effect = Exception("DB connection lost")

        with pytest.raises(Exception, match="DB connection lost"):
            await svc.create_alert(alert_type="test_type")


# ═══════════════════════════════════════════════════════════════════════════════
# check_deadline_alerts
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckDeadlineAlerts:
    """Tests for check_deadline_alerts — redemption and auction windows."""

    @pytest.mark.asyncio
    async def test_finds_redemption_deadlines(self) -> None:
        """check_deadline_alerts creates alerts for approaching redemption deadlines."""
        svc, session = _make_service()
        today = date.today()
        deadline = today + timedelta(days=15)

        lien = _make_lien(
            parcel_id="P-REDEMPTION",
            redemption_deadline=deadline,
            certificate_number="CERT-R1",
        )

        # First execute: redemption query returns [lien]
        redemption_result = MagicMock()
        redemption_result.scalars.return_value.all.return_value = [lien]
        # Second execute: auction query returns []
        auction_result = MagicMock()
        auction_result.scalars.return_value.all.return_value = []

        session.execute.side_effect = [redemption_result, auction_result]

        # Mock create_alert and session.get for alert retrieval
        alert_mock = MagicMock()
        alert_mock.id = 100
        alert_mock.alert_type = "redemption_deadline"

        alert_counter = [0]
        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def fake_flush():
            if added_objects:
                alert_counter[0] += 1
                added_objects[-1].id = 100 + alert_counter[0]

        session.flush.side_effect = fake_flush
        session.get = AsyncMock(return_value=alert_mock)

        alerts = await svc.check_deadline_alerts(days_ahead=30)

        assert len(alerts) == 1
        assert alerts[0].alert_type == "redemption_deadline"
        session.add.assert_called()

    @pytest.mark.asyncio
    async def test_finds_auction_dates(self) -> None:
        """check_deadline_alerts creates alerts for approaching auction dates."""
        svc, session = _make_service()
        today = date.today()
        auction = today + timedelta(days=10)

        lien = _make_lien(
            parcel_id="P-AUCTION",
            auction_date=auction,
            auction_platform="GovDeals",
        )

        # First execute: redemption returns []
        redemption_result = MagicMock()
        redemption_result.scalars.return_value.all.return_value = []
        # Second execute: auction returns [lien]
        auction_result = MagicMock()
        auction_result.scalars.return_value.all.return_value = [lien]

        session.execute.side_effect = [redemption_result, auction_result]

        alert_mock = MagicMock()
        alert_mock.id = 200
        alert_mock.alert_type = "auction_date"

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def fake_flush():
            if added_objects:
                added_objects[-1].id = 200

        session.flush.side_effect = fake_flush
        session.get = AsyncMock(return_value=alert_mock)

        alerts = await svc.check_deadline_alerts(days_ahead=30)

        assert len(alerts) == 1
        assert alerts[0].alert_type == "auction_date"

    @pytest.mark.asyncio
    async def test_no_deadlines_returns_empty(self) -> None:
        """check_deadline_alerts returns [] when no deadlines are approaching."""
        svc, session = _make_service()

        empty_result = MagicMock()
        empty_result.scalars.return_value.all.return_value = []
        session.execute.side_effect = [empty_result, empty_result]

        alerts = await svc.check_deadline_alerts()
        assert alerts == []

    @pytest.mark.asyncio
    async def test_both_redemption_and_auction(self) -> None:
        """check_deadline_alerts handles both redemption and auction at once."""
        svc, session = _make_service()
        today = date.today()

        red_lien = _make_lien(
            parcel_id="P-RED",
            redemption_deadline=today + timedelta(days=5),
        )
        auc_lien = _make_lien(
            parcel_id="P-AUC",
            auction_date=today + timedelta(days=20),
            auction_platform="RealAuction",
        )

        redemption_result = MagicMock()
        redemption_result.scalars.return_value.all.return_value = [red_lien]
        auction_result = MagicMock()
        auction_result.scalars.return_value.all.return_value = [auc_lien]

        session.execute.side_effect = [redemption_result, auction_result]

        alert_counter = [0]
        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def fake_flush():
            if added_objects:
                alert_counter[0] += 1
                added_objects[-1].id = alert_counter[0]

        session.flush.side_effect = fake_flush

        red_alert = MagicMock()
        red_alert.alert_type = "redemption_deadline"
        auc_alert = MagicMock()
        auc_alert.alert_type = "auction_date"

        session.get = AsyncMock(side_effect=[red_alert, auc_alert])

        alerts = await svc.check_deadline_alerts()
        assert len(alerts) == 2

    @pytest.mark.asyncio
    async def test_alert_message_contains_days_and_date(self) -> None:
        """Alert message includes days remaining and the ISO date."""
        svc, session = _make_service()
        today = date.today()
        deadline = today + timedelta(days=7)

        lien = _make_lien(
            parcel_id="P-MSG",
            redemption_deadline=deadline,
            certificate_number="CERT-MSG",
        )

        redemption_result = MagicMock()
        redemption_result.scalars.return_value.all.return_value = [lien]
        auction_result = MagicMock()
        auction_result.scalars.return_value.all.return_value = []
        session.execute.side_effect = [redemption_result, auction_result]

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def fake_flush():
            if added_objects:
                added_objects[-1].id = 50

        session.flush.side_effect = fake_flush
        session.get = AsyncMock(return_value=MagicMock())

        await svc.check_deadline_alerts()

        # Check the alert that was added via session.add
        alert_obj = added_objects[0]
        assert "7 days" in alert_obj.message
        assert deadline.isoformat() in alert_obj.message
        assert "CERT-MSG" in alert_obj.message

    @pytest.mark.asyncio
    async def test_auction_alert_includes_platform(self) -> None:
        """Auction alert message includes platform name."""
        svc, session = _make_service()
        today = date.today()
        auc_date = today + timedelta(days=3)

        lien = _make_lien(
            parcel_id="P-PLAT",
            auction_date=auc_date,
            auction_platform="GovDeals",
        )

        redemption_result = MagicMock()
        redemption_result.scalars.return_value.all.return_value = []
        auction_result = MagicMock()
        auction_result.scalars.return_value.all.return_value = [lien]
        session.execute.side_effect = [redemption_result, auction_result]

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def fake_flush():
            if added_objects:
                added_objects[-1].id = 60

        session.flush.side_effect = fake_flush
        session.get = AsyncMock(return_value=MagicMock())

        await svc.check_deadline_alerts()

        alert_obj = added_objects[0]
        assert "GovDeals" in alert_obj.message

    @pytest.mark.asyncio
    async def test_auction_alert_unknown_platform(self) -> None:
        """Auction alert says 'unknown platform' when platform is None."""
        svc, session = _make_service()
        today = date.today()

        lien = _make_lien(
            parcel_id="P-NOPLAT",
            auction_date=today + timedelta(days=2),
            auction_platform=None,
        )

        redemption_result = MagicMock()
        redemption_result.scalars.return_value.all.return_value = []
        auction_result = MagicMock()
        auction_result.scalars.return_value.all.return_value = [lien]
        session.execute.side_effect = [redemption_result, auction_result]

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def fake_flush():
            if added_objects:
                added_objects[-1].id = 70

        session.flush.side_effect = fake_flush
        session.get = AsyncMock(return_value=MagicMock())

        await svc.check_deadline_alerts()

        alert_obj = added_objects[0]
        assert "unknown platform" in alert_obj.message

    @pytest.mark.asyncio
    async def test_session_get_returns_none_skips_alert(self) -> None:
        """When session.get returns None after create_alert, alert is not appended."""
        svc, session = _make_service()
        today = date.today()

        lien = _make_lien(
            parcel_id="P-SKIP",
            redemption_deadline=today + timedelta(days=10),
        )

        redemption_result = MagicMock()
        redemption_result.scalars.return_value.all.return_value = [lien]
        auction_result = MagicMock()
        auction_result.scalars.return_value.all.return_value = []
        session.execute.side_effect = [redemption_result, auction_result]

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def fake_flush():
            if added_objects:
                added_objects[-1].id = 80

        session.flush.side_effect = fake_flush
        # session.get returns None (alert wasn't persisted)
        session.get = AsyncMock(return_value=None)

        alerts = await svc.check_deadline_alerts()
        assert alerts == []

    @pytest.mark.asyncio
    async def test_custom_days_ahead(self) -> None:
        """check_deadline_alerts respects custom days_ahead parameter."""
        svc, session = _make_service()

        empty_result = MagicMock()
        empty_result.scalars.return_value.all.return_value = []
        session.execute.side_effect = [empty_result, empty_result]

        # Just verify it doesn't crash with a different window
        alerts = await svc.check_deadline_alerts(days_ahead=7)
        assert alerts == []
        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_redemption_no_certificate_number(self) -> None:
        """Redemption alert uses 'N/A' when certificate_number is None."""
        svc, session = _make_service()
        today = date.today()

        lien = _make_lien(
            parcel_id="P-NOCERT",
            redemption_deadline=today + timedelta(days=5),
            certificate_number=None,
        )

        redemption_result = MagicMock()
        redemption_result.scalars.return_value.all.return_value = [lien]
        auction_result = MagicMock()
        auction_result.scalars.return_value.all.return_value = []
        session.execute.side_effect = [redemption_result, auction_result]

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def fake_flush():
            if added_objects:
                added_objects[-1].id = 90

        session.flush.side_effect = fake_flush
        session.get = AsyncMock(return_value=MagicMock())

        await svc.check_deadline_alerts()

        alert_obj = added_objects[0]
        assert "N/A" in alert_obj.message


# ═══════════════════════════════════════════════════════════════════════════════
# send_scan_complete — additional edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestSendScanComplete:
    """Additional edge-case tests beyond the basics in test_services.py."""

    @pytest.mark.asyncio
    async def test_subject_includes_county_and_state(self) -> None:
        """Email subject includes formatted county and state."""
        svc, session = _make_service()
        mock_settings = MagicMock()
        mock_settings.sendgrid_api_key = "SG.test"
        mock_settings.sendgrid_from_email = "noreply@aloha.com"

        mock_response = MagicMock()
        mock_response.headers = {"X-Message-Id": "msg-1"}
        mock_response.raise_for_status = MagicMock()

        with (
            patch("aloha.config.settings", mock_settings),
            patch("httpx.AsyncClient") as MockClient,
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            await svc.send_scan_complete("user@test.com", "fl", "miami-dade", 100)

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert "Miami-Dade" in payload["subject"]
        assert "FL" in payload["subject"]

    @pytest.mark.asyncio
    async def test_body_includes_parcel_count(self) -> None:
        """Email body includes the parcels-found count."""
        svc, session = _make_service()
        mock_settings = MagicMock()
        mock_settings.sendgrid_api_key = "SG.test"
        mock_settings.sendgrid_from_email = "noreply@aloha.com"

        mock_response = MagicMock()
        mock_response.headers = {"X-Message-Id": "msg-2"}
        mock_response.raise_for_status = MagicMock()

        with (
            patch("aloha.config.settings", mock_settings),
            patch("httpx.AsyncClient") as MockClient,
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            await svc.send_scan_complete("user@test.com", "FL", "orange", 42)

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert "42" in payload["content"][0]["value"]

    @pytest.mark.asyncio
    async def test_authorization_header_contains_api_key(self) -> None:
        """SendGrid POST includes the correct Authorization header."""
        svc, session = _make_service()
        mock_settings = MagicMock()
        mock_settings.sendgrid_api_key = "SG.my-secret-key"
        mock_settings.sendgrid_from_email = "noreply@aloha.com"

        mock_response = MagicMock()
        mock_response.headers = {"X-Message-Id": "msg-3"}
        mock_response.raise_for_status = MagicMock()

        with (
            patch("aloha.config.settings", mock_settings),
            patch("httpx.AsyncClient") as MockClient,
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            await svc.send_scan_complete("user@test.com", "FL", "orange", 1)

        call_args = mock_client.post.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers")
        assert headers["Authorization"] == "Bearer SG.my-secret-key"
