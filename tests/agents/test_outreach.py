"""Unit tests for the Outreach Agent (no DB, no LLM, no network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aloha.agents.outreach.tools import (
    build_template_variables,
    choose_template,
    format_outreach_summary,
    select_channels,
    should_skip_outreach,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Tests — pure functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestSelectChannels:
    def test_email_and_sms(self):
        channels = select_channels(best_phone="+15551234567", best_email="a@b.com")
        assert "email" in channels
        assert "sms" in channels

    def test_email_only(self):
        channels = select_channels(best_phone=None, best_email="a@b.com")
        assert channels == ["email"]

    def test_phone_only(self):
        channels = select_channels(best_phone="+15551234567", best_email=None)
        assert "sms" in channels

    def test_no_contact(self):
        channels = select_channels(best_phone=None, best_email=None)
        assert channels == []

    def test_phone_call_with_high_score(self):
        channels = select_channels(
            best_phone="+15551234567", best_email="a@b.com", reachability_score=5
        )
        assert "phone_call" in channels

    def test_no_phone_call_with_low_score(self):
        channels = select_channels(
            best_phone="+15551234567", best_email="a@b.com", reachability_score=3
        )
        assert "phone_call" not in channels


class TestBuildTemplateVariables:
    def test_full_data(self):
        result = build_template_variables(
            owner_name="SMITH, JOHN",
            property_address="123 Main St",
            county="miami-dade",
            state="fl",
            tax_amount=4200.50,
            sale_date="2024-06-15",
            instrument_type="lien_certificate",
        )
        assert result["owner_name"] == "SMITH, JOHN"
        assert result["first_name"] == "John"
        assert result["property_address"] == "123 Main St"
        assert result["county"] == "Miami-Dade"
        assert result["state"] == "FL"
        assert result["tax_amount"] == "$4,200.50"
        assert result["sale_date"] == "2024-06-15"
        assert result["instrument_type"] == "lien_certificate"

    def test_missing_values_use_defaults(self):
        result = build_template_variables(
            owner_name=None,
            property_address=None,
            county=None,
            state=None,
        )
        assert result["owner_name"] == "Property Owner"
        assert result["first_name"] == "there"
        assert result["property_address"] == "your property"
        assert result["tax_amount"] == "the outstanding amount"

    def test_first_last_name_format(self):
        result = build_template_variables(
            owner_name="John Smith",
            property_address=None,
            county=None,
            state=None,
        )
        assert result["first_name"] == "John"


class TestChooseTemplate:
    def test_email_initial(self):
        name = choose_template(channel="email", instrument_type="lien_certificate")
        assert name == "email_lien_initial"

    def test_sms_followup(self):
        name = choose_template(channel="sms", instrument_type="tax_deed", attempt_number=2)
        assert name == "sms_deed_followup_2"

    def test_default_instrument(self):
        name = choose_template(channel="email")
        assert name == "email_lien_initial"

    def test_followup_capped_at_3(self):
        name = choose_template(channel="email", attempt_number=5)
        assert name == "email_lien_followup_3"


class TestShouldSkipOutreach:
    def test_government_owner(self):
        result = should_skip_outreach(
            owner_type="government", best_phone="+1555", best_email="a@b.com"
        )
        assert result["skip"] is True
        assert "government" in result["reason"]

    def test_no_contact_info(self):
        result = should_skip_outreach(
            owner_type="individual", best_phone=None, best_email=None
        )
        assert result["skip"] is True

    def test_valid_owner(self):
        result = should_skip_outreach(
            owner_type="individual", best_phone="+1555", best_email="a@b.com"
        )
        assert result["skip"] is False


class TestFormatOutreachSummary:
    def test_mixed_results(self):
        results = [
            {"channel": "email", "status": "scheduled", "outreach_id": 1},
            {"channel": "sms", "status": "skipped", "reason": "DNC"},
            {"channel": "phone_call", "status": "failed", "error": "timeout"},
        ]
        summary = format_outreach_summary(results)
        assert summary["total_attempts"] == 3
        assert summary["scheduled"] == 1
        assert summary["skipped"] == 1
        assert summary["failed"] == 1
        assert "email" in summary["channels_used"]
        assert "DNC" in summary["skip_reasons"]
        assert "timeout" in summary["errors"]

    def test_all_scheduled(self):
        results = [
            {"channel": "email", "status": "scheduled"},
            {"channel": "sms", "status": "scheduled"},
        ]
        summary = format_outreach_summary(results)
        assert summary["scheduled"] == 2
        assert summary["failed"] == 0

    def test_empty(self):
        summary = format_outreach_summary([])
        assert summary["total_attempts"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Agent Tests — mocked DB and services
# ═══════════════════════════════════════════════════════════════════════════════


class TestOutreachAgent:
    @pytest.fixture
    def agent(self):
        with patch("aloha.agents.base.get_agent_model", return_value="test-model"):
            from aloha.agents.outreach.agent import OutreachAgent
            return OutreachAgent()

    @pytest.fixture
    def base_context(self):
        return {
            "parcel_id": "TEST-001",
            "owner_id": 42,
            "user_id": "user-uuid-123",
            "state": "FL",
            "county": "miami-dade",
            "owner_name": "SMITH, JOHN",
            "owner_type": "individual",
            "best_phone": "+15551234567",
            "best_email": "john@example.com",
            "property_address": "123 Main St",
        }

    @pytest.mark.asyncio
    async def test_full_flow_schedules_channels(self, agent, base_context):
        agent._load_owner = AsyncMock(return_value={
            "owner_name": "SMITH, JOHN",
            "owner_type": "individual",
            "best_phone": "+15551234567",
            "best_email": "john@example.com",
            "address": "123 Main St",
            "reachability_score": 3,
        })
        agent._schedule_channel = AsyncMock(return_value={
            "channel": "email",
            "status": "scheduled",
            "outreach_id": 1,
        })
        agent._advance_parcel = AsyncMock()

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        assert result["summary"]["scheduled"] > 0
        agent._advance_parcel.assert_called_once()

    @pytest.mark.asyncio
    async def test_government_owner_skipped(self, agent, base_context):
        base_context["owner_type"] = "government"
        agent._load_owner = AsyncMock(return_value={
            "owner_type": "government",
            "best_phone": "+15551234567",
            "best_email": "gov@example.com",
        })

        result = await agent.run(base_context)

        assert result["status"] == "skipped"
        assert "government" in result["reason"]

    @pytest.mark.asyncio
    async def test_no_contact_info_skipped(self, agent, base_context):
        base_context.pop("best_phone")
        base_context.pop("best_email")
        agent._load_owner = AsyncMock(return_value={
            "owner_name": "SMITH, JOHN",
            "owner_type": "individual",
            "best_phone": None,
            "best_email": None,
        })

        result = await agent.run(base_context)

        assert result["status"] == "skipped"
        assert "no contact" in result["reason"]

    @pytest.mark.asyncio
    async def test_loads_owner_from_db(self, agent, base_context):
        base_context.pop("owner_name", None)
        base_context.pop("best_phone", None)
        base_context.pop("best_email", None)
        agent._load_owner = AsyncMock(return_value={
            "owner_name": "DOE, JANE",
            "owner_type": "individual",
            "best_phone": "+15559876543",
            "best_email": "jane@example.com",
            "address": "456 Oak Ave",
            "reachability_score": 5,
        })
        agent._schedule_channel = AsyncMock(return_value={
            "channel": "email",
            "status": "scheduled",
            "outreach_id": 2,
        })
        agent._advance_parcel = AsyncMock()

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        agent._load_owner.assert_called_once_with(42)

    @pytest.mark.asyncio
    async def test_schedule_failure_handled(self, agent, base_context):
        agent._load_owner = AsyncMock(return_value={
            "owner_name": "SMITH, JOHN",
            "owner_type": "individual",
            "best_phone": "+15551234567",
            "best_email": "john@example.com",
            "reachability_score": 3,
        })
        # First channel succeeds, second fails
        agent._schedule_channel = AsyncMock(side_effect=[
            {"channel": "email", "status": "scheduled", "outreach_id": 1},
            {"channel": "sms", "status": "failed", "error": "service unavailable"},
        ])
        agent._advance_parcel = AsyncMock()

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        assert result["summary"]["scheduled"] == 1
        assert result["summary"]["failed"] == 1
