"""Comprehensive tests for the OutreachService.

Covers frequency caps, schedule_outreach full lifecycle, approve_outreach,
_render_from_db template rendering, and edge cases.

Existing tests in test_services.py cover:
  - check_dnc (found / not found)
  - schedule_outreach (DNC-blocked path)
  - render_template (static)
  - send_outreach (email/SMS/stub/not-approved/not-found)
This file focuses on the remaining uncovered methods and edge cases.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aloha.core.exceptions import OutreachBlockedError
from aloha.services.outreach_service import OutreachService


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_service(session: AsyncMock | None = None) -> tuple[OutreachService, AsyncMock]:
    """Instantiate OutreachService with a mocked session."""
    session = session or AsyncMock()
    session.add = MagicMock()
    svc = OutreachService(session)
    return svc, session


# ═══════════════════════════════════════════════════════════════════════════════
# check_frequency_cap
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckFrequencyCap:
    """Tests for check_frequency_cap."""

    @pytest.mark.asyncio
    async def test_frequency_cap_exceeded(self) -> None:
        """Returns True when owner was contacted within the cap window."""
        svc, session = _make_service()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 2  # 2 recent contacts
        session.execute.return_value = mock_result

        assert await svc.check_frequency_cap("user-1", 42, "email") is True

    @pytest.mark.asyncio
    async def test_frequency_cap_not_exceeded(self) -> None:
        """Returns False when no recent contacts exist."""
        svc, session = _make_service()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        session.execute.return_value = mock_result

        assert await svc.check_frequency_cap("user-1", 42, "email") is False

    @pytest.mark.asyncio
    async def test_frequency_cap_exactly_one_contact(self) -> None:
        """Returns True when exactly one contact exists within window."""
        svc, session = _make_service()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 1
        session.execute.return_value = mock_result

        assert await svc.check_frequency_cap("user-1", 42, "sms") is True

    @pytest.mark.asyncio
    async def test_frequency_cap_different_channels(self) -> None:
        """Frequency cap is per-channel — different channels don't interfere."""
        svc, session = _make_service()

        # First call (email): no contacts
        # Second call (sms): has contacts
        email_result = MagicMock()
        email_result.scalar_one.return_value = 0
        sms_result = MagicMock()
        sms_result.scalar_one.return_value = 1
        session.execute.side_effect = [email_result, sms_result]

        assert await svc.check_frequency_cap("user-1", 42, "email") is False
        assert await svc.check_frequency_cap("user-1", 42, "sms") is True


# ═══════════════════════════════════════════════════════════════════════════════
# schedule_outreach — success path
# ═══════════════════════════════════════════════════════════════════════════════


class TestScheduleOutreach:
    """Tests for schedule_outreach beyond the DNC-blocked case."""

    @pytest.mark.asyncio
    async def test_schedule_happy_path(self) -> None:
        """schedule_outreach creates a pending log entry on success."""
        svc, session = _make_service()

        # DNC check: not found
        dnc_result = MagicMock()
        dnc_result.scalar_one.return_value = 0
        # Frequency cap: not exceeded
        freq_result = MagicMock()
        freq_result.scalar_one.return_value = 0
        session.execute.side_effect = [dnc_result, freq_result]

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def fake_flush():
            if added_objects:
                added_objects[-1].id = 42

        session.flush.side_effect = fake_flush

        result_id = await svc.schedule_outreach(
            user_id="user-1",
            parcel_id="P001",
            owner_id=10,
            channel="email",
            contact_value="owner@example.com",
        )

        assert result_id == 42
        log_entry = added_objects[0]
        assert log_entry.status == "pending"
        assert log_entry.channel == "email"
        assert log_entry.contact_value == "owner@example.com"

    @pytest.mark.asyncio
    async def test_schedule_blocked_by_frequency_cap(self) -> None:
        """schedule_outreach raises OutreachBlockedError on frequency cap."""
        svc, session = _make_service()

        # DNC check: not found
        dnc_result = MagicMock()
        dnc_result.scalar_one.return_value = 0
        # Frequency cap: exceeded
        freq_result = MagicMock()
        freq_result.scalar_one.return_value = 1
        session.execute.side_effect = [dnc_result, freq_result]

        with pytest.raises(OutreachBlockedError, match="already contacted"):
            await svc.schedule_outreach(
                user_id="user-1",
                parcel_id="P001",
                owner_id=10,
                channel="email",
                contact_value="owner@example.com",
            )

    @pytest.mark.asyncio
    async def test_schedule_with_template_rendering(self) -> None:
        """schedule_outreach renders template when template_name is given."""
        svc, session = _make_service()

        # DNC: not found
        dnc_result = MagicMock()
        dnc_result.scalar_one.return_value = 0
        # Frequency: not exceeded
        freq_result = MagicMock()
        freq_result.scalar_one.return_value = 0
        # Template lookup
        mock_template = MagicMock()
        mock_template.subject = "Hello {{ name }}"
        mock_template.body = "Your parcel {{ parcel_id }} is ready."
        tpl_result = MagicMock()
        tpl_result.scalars.return_value.first.return_value = mock_template

        session.execute.side_effect = [dnc_result, freq_result, tpl_result]

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def fake_flush():
            if added_objects:
                added_objects[-1].id = 100

        session.flush.side_effect = fake_flush

        result_id = await svc.schedule_outreach(
            user_id="user-1",
            parcel_id="P001",
            owner_id=10,
            channel="email",
            contact_value="owner@example.com",
            template_name="intro_email",
            variables={"name": "John", "parcel_id": "P001"},
        )

        assert result_id == 100
        log_entry = added_objects[0]
        assert log_entry.subject == "Hello John"
        assert log_entry.message_body == "Your parcel P001 is ready."

    @pytest.mark.asyncio
    async def test_schedule_with_missing_template(self) -> None:
        """schedule_outreach handles missing template gracefully."""
        svc, session = _make_service()

        # DNC: not found
        dnc_result = MagicMock()
        dnc_result.scalar_one.return_value = 0
        # Frequency: not exceeded
        freq_result = MagicMock()
        freq_result.scalar_one.return_value = 0
        # Template not found
        tpl_result = MagicMock()
        tpl_result.scalars.return_value.first.return_value = None
        session.execute.side_effect = [dnc_result, freq_result, tpl_result]

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def fake_flush():
            if added_objects:
                added_objects[-1].id = 101

        session.flush.side_effect = fake_flush

        result_id = await svc.schedule_outreach(
            user_id="user-1",
            parcel_id="P001",
            owner_id=10,
            channel="email",
            contact_value="owner@example.com",
            template_name="nonexistent_template",
        )

        assert result_id == 101
        log_entry = added_objects[0]
        assert log_entry.subject is None
        assert log_entry.message_body is None

    @pytest.mark.asyncio
    async def test_schedule_without_template(self) -> None:
        """schedule_outreach without template_name leaves body/subject None."""
        svc, session = _make_service()

        dnc_result = MagicMock()
        dnc_result.scalar_one.return_value = 0
        freq_result = MagicMock()
        freq_result.scalar_one.return_value = 0
        session.execute.side_effect = [dnc_result, freq_result]

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def fake_flush():
            if added_objects:
                added_objects[-1].id = 102

        session.flush.side_effect = fake_flush

        await svc.schedule_outreach(
            user_id="user-1",
            parcel_id=None,
            owner_id=10,
            channel="sms",
            contact_value="+15551234567",
        )

        log_entry = added_objects[0]
        assert log_entry.template_name is None
        assert log_entry.message_body is None
        assert log_entry.subject is None

    @pytest.mark.asyncio
    async def test_schedule_sms_uses_phone_contact_type(self) -> None:
        """For SMS channel, DNC check uses 'phone' contact_type."""
        svc, session = _make_service()

        # DNC: not found
        dnc_result = MagicMock()
        dnc_result.scalar_one.return_value = 0
        # Frequency: not exceeded
        freq_result = MagicMock()
        freq_result.scalar_one.return_value = 0
        session.execute.side_effect = [dnc_result, freq_result]

        added_objects: list = []
        session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def fake_flush():
            if added_objects:
                added_objects[-1].id = 103

        session.flush.side_effect = fake_flush

        await svc.schedule_outreach(
            user_id="user-1",
            parcel_id="P001",
            owner_id=10,
            channel="sms",
            contact_value="+15551234567",
        )

        # Verify the DNC query was executed (first call)
        assert session.execute.call_count == 2


# ═══════════════════════════════════════════════════════════════════════════════
# approve_outreach
# ═══════════════════════════════════════════════════════════════════════════════


class TestApproveOutreach:
    """Tests for approve_outreach."""

    @pytest.mark.asyncio
    async def test_approve_happy_path(self) -> None:
        """approve_outreach sets status to 'approved' and records timestamp."""
        svc, session = _make_service()
        entry = MagicMock()
        entry.status = "pending"
        entry.approved_at = None
        session.get = AsyncMock(return_value=entry)

        await svc.approve_outreach(42)

        assert entry.status == "approved"
        assert entry.approved_at is not None
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_approve_not_found_raises(self) -> None:
        """approve_outreach raises ValueError when entry doesn't exist."""
        svc, session = _make_service()
        session.get = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await svc.approve_outreach(999)

    @pytest.mark.asyncio
    async def test_approve_sets_utc_timestamp(self) -> None:
        """approve_outreach sets approved_at to a UTC datetime."""
        svc, session = _make_service()
        entry = MagicMock()
        entry.status = "pending"
        entry.approved_at = None
        session.get = AsyncMock(return_value=entry)

        before = datetime.now(tz=timezone.utc)
        await svc.approve_outreach(42)
        after = datetime.now(tz=timezone.utc)

        assert entry.approved_at.tzinfo is not None
        assert before <= entry.approved_at <= after


# ═══════════════════════════════════════════════════════════════════════════════
# _render_from_db
# ═══════════════════════════════════════════════════════════════════════════════


class TestRenderFromDb:
    """Tests for _render_from_db template loading and rendering."""

    @pytest.mark.asyncio
    async def test_renders_template_from_db(self) -> None:
        """_render_from_db loads and renders a template with variables."""
        svc, session = _make_service()

        mock_tpl = MagicMock()
        mock_tpl.subject = "Offer for {{ parcel_id }}"
        mock_tpl.body = "Dear {{ name }}, your property at {{ address }}."
        mock_tpl.is_active = True

        tpl_result = MagicMock()
        tpl_result.scalars.return_value.first.return_value = mock_tpl
        session.execute.return_value = tpl_result

        result = await svc._render_from_db(
            "intro_email",
            {"parcel_id": "P001", "name": "Jane", "address": "123 Main St"},
        )

        assert result["subject"] == "Offer for P001"
        assert "Jane" in result["body"]
        assert "123 Main St" in result["body"]

    @pytest.mark.asyncio
    async def test_template_not_found_returns_nones(self) -> None:
        """_render_from_db returns {subject: None, body: None} for missing templates."""
        svc, session = _make_service()

        tpl_result = MagicMock()
        tpl_result.scalars.return_value.first.return_value = None
        session.execute.return_value = tpl_result

        result = await svc._render_from_db("nonexistent", {"name": "Test"})

        assert result["subject"] is None
        assert result["body"] is None

    @pytest.mark.asyncio
    async def test_template_with_none_body(self) -> None:
        """_render_from_db handles template with body=None."""
        svc, session = _make_service()

        mock_tpl = MagicMock()
        mock_tpl.subject = "Subject line"
        mock_tpl.body = None

        tpl_result = MagicMock()
        tpl_result.scalars.return_value.first.return_value = mock_tpl
        session.execute.return_value = tpl_result

        result = await svc._render_from_db("partial_template", {})

        assert result["subject"] == "Subject line"
        assert result["body"] is None

    @pytest.mark.asyncio
    async def test_template_with_none_subject(self) -> None:
        """_render_from_db handles template with subject=None."""
        svc, session = _make_service()

        mock_tpl = MagicMock()
        mock_tpl.subject = None
        mock_tpl.body = "Body text {{ var }}"

        tpl_result = MagicMock()
        tpl_result.scalars.return_value.first.return_value = mock_tpl
        session.execute.return_value = tpl_result

        result = await svc._render_from_db("sms_template", {"var": "value"})

        assert result["subject"] is None
        assert result["body"] == "Body text value"


# ═══════════════════════════════════════════════════════════════════════════════
# render_template — additional edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestRenderTemplateEdgeCases:
    """Edge cases for the static render_template method."""

    def test_render_empty_variables(self) -> None:
        """Rendering with no variables works for plain text."""
        result = OutreachService.render_template("Hello world!", {})
        assert result == "Hello world!"

    def test_render_missing_variable_leaves_empty(self) -> None:
        """Jinja2 renders missing variables as empty string by default."""
        result = OutreachService.render_template(
            "Hello {{ name }}, status: {{ status }}",
            {"name": "John"},
        )
        assert "John" in result
        assert "status:" in result

    def test_render_special_characters(self) -> None:
        """Template rendering handles special characters."""
        result = OutreachService.render_template(
            "Price: ${{ amount }} for {{ addr }}",
            {"amount": "5,000", "addr": "123 O'Brien St"},
        )
        assert "$5,000" in result
        assert "O'Brien" in result


# ═══════════════════════════════════════════════════════════════════════════════
# send_outreach — HTTP error handling
# ═══════════════════════════════════════════════════════════════════════════════


class TestSendOutreachErrors:
    """Tests for send_outreach error paths."""

    @pytest.mark.asyncio
    async def test_send_email_http_error_propagates(self) -> None:
        """send_outreach propagates HTTP errors from SendGrid."""
        import httpx

        svc, session = _make_service()
        entry = MagicMock()
        entry.channel = "email"
        entry.status = "approved"
        entry.contact_value = "user@test.com"
        entry.subject = "Test"
        entry.message_body = "Body"
        session.get = AsyncMock(return_value=entry)

        mock_settings = MagicMock()
        mock_settings.sendgrid_api_key = "SG.test"
        mock_settings.sendgrid_from_email = "noreply@aloha.com"

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=MagicMock()
        )

        with (
            patch("aloha.config.settings", mock_settings),
            patch("httpx.AsyncClient") as MockClient,
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await svc.send_outreach(42)

    @pytest.mark.asyncio
    async def test_send_sms_http_error_propagates(self) -> None:
        """send_outreach propagates HTTP errors from Twilio."""
        import httpx

        svc, session = _make_service()
        entry = MagicMock()
        entry.channel = "sms"
        entry.status = "approved"
        entry.contact_value = "+15551234567"
        entry.message_body = "Test message"
        session.get = AsyncMock(return_value=entry)

        mock_settings = MagicMock()
        mock_settings.twilio_account_sid = "ACtest"
        mock_settings.twilio_auth_token = "auth-token"
        mock_settings.twilio_phone_number = "+15559876543"

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock()
        )

        with (
            patch("aloha.config.settings", mock_settings),
            patch("httpx.AsyncClient") as MockClient,
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await svc.send_outreach(43)

    @pytest.mark.asyncio
    async def test_send_voicemail_uses_twilio(self) -> None:
        """send_outreach routes 'voicemail' channel through Twilio."""
        svc, session = _make_service()
        entry = MagicMock()
        entry.channel = "voicemail"
        entry.status = "approved"
        entry.contact_value = "+15551234567"
        entry.message_body = "Please call back."
        session.get = AsyncMock(return_value=entry)

        mock_settings = MagicMock()
        mock_settings.twilio_account_sid = None
        mock_settings.twilio_auth_token = None
        mock_settings.twilio_phone_number = None

        with patch("aloha.config.settings", mock_settings):
            await svc.send_outreach(44)

        assert entry.provider == "twilio"
        assert entry.provider_msg_id == "stub_no_twilio_creds"
        assert entry.status == "sent"
