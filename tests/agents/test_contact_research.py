"""Unit tests for the Contact Research Agent (no DB, no LLM, no network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aloha.agents.contact_research.tools import (
    normalise_email,
    normalise_phone,
    pick_best_contact,
    score_contact_quality,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Tests — pure functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestNormalisePhone:
    def test_ten_digit(self):
        assert normalise_phone("5551234567") == "+15551234567"

    def test_with_parens_and_dashes(self):
        assert normalise_phone("(555) 123-4567") == "+15551234567"

    def test_with_dashes(self):
        assert normalise_phone("555-123-4567") == "+15551234567"

    def test_eleven_digit_with_1(self):
        assert normalise_phone("15551234567") == "+15551234567"

    def test_already_e164(self):
        assert normalise_phone("+15551234567") == "+15551234567"

    def test_too_short(self):
        assert normalise_phone("12345") is None

    def test_too_long(self):
        assert normalise_phone("123456789012") is None

    def test_none(self):
        assert normalise_phone(None) is None

    def test_empty(self):
        assert normalise_phone("") is None


class TestNormaliseEmail:
    def test_basic(self):
        assert normalise_email("User@Example.COM") == "user@example.com"

    def test_with_whitespace(self):
        assert normalise_email("  user@example.com  ") == "user@example.com"

    def test_invalid_no_at(self):
        assert normalise_email("not-an-email") is None

    def test_invalid_no_domain(self):
        assert normalise_email("user@") is None

    def test_none(self):
        assert normalise_email(None) is None

    def test_empty(self):
        assert normalise_email("") is None

    def test_plus_addressing(self):
        assert normalise_email("user+tag@example.com") == "user+tag@example.com"


class TestScoreContactQuality:
    def test_both_verified_mobile(self):
        result = score_contact_quality(
            has_phone=True, has_email=True, email_verified=True, phone_type="mobile"
        )
        assert result["score"] == 10
        assert "email" in result["channels"]
        assert "phone" in result["channels"]

    def test_email_only_unverified(self):
        result = score_contact_quality(has_phone=False, has_email=True)
        assert result["score"] == 3
        assert result["channels"] == ["email"]

    def test_phone_only_landline(self):
        result = score_contact_quality(
            has_phone=True, has_email=False, phone_type="landline"
        )
        assert result["score"] == 4  # 3 + 1 landline
        assert "sms" in result["channels"]

    def test_no_contact(self):
        result = score_contact_quality(has_phone=False, has_email=False)
        assert result["score"] == 0
        assert "no contact info found" in result["notes"]

    def test_phone_unknown_type(self):
        result = score_contact_quality(has_phone=True, has_email=False)
        assert result["score"] == 3


class TestPickBestContact:
    def test_phone_and_email_dicts(self):
        data = {
            "phone_numbers": [
                {"number": "5551234567", "type": "landline"},
                {"number": "5559876543", "type": "mobile"},
            ],
            "emails": [
                {"address": "John@Example.com"},
            ],
        }
        result = pick_best_contact(data)
        assert result["best_phone"] == "+15559876543"  # mobile preferred
        assert result["phone_type"] == "mobile"
        assert result["best_email"] == "john@example.com"

    def test_phone_strings(self):
        data = {
            "phone_numbers": ["(555) 111-2222"],
            "emails": ["test@test.com"],
        }
        result = pick_best_contact(data)
        assert result["best_phone"] == "+15551112222"
        assert result["best_email"] == "test@test.com"

    def test_empty_enrichment(self):
        result = pick_best_contact({})
        assert result["best_phone"] is None
        assert result["best_email"] is None
        assert result["phone_type"] is None

    def test_invalid_phone_skipped(self):
        data = {"phone_numbers": [{"number": "123", "type": "mobile"}], "emails": []}
        result = pick_best_contact(data)
        assert result["best_phone"] is None

    def test_invalid_email_skipped(self):
        data = {"phone_numbers": [], "emails": ["not-an-email"]}
        result = pick_best_contact(data)
        assert result["best_email"] is None

    def test_first_valid_email_wins(self):
        data = {
            "phone_numbers": [],
            "emails": ["bad", "good@example.com", "also@good.com"],
        }
        result = pick_best_contact(data)
        assert result["best_email"] == "good@example.com"


# ═══════════════════════════════════════════════════════════════════════════════
# Agent Tests — mocked DB and MCP
# ═══════════════════════════════════════════════════════════════════════════════


class TestContactResearchAgent:
    @pytest.fixture
    def agent(self):
        with patch("aloha.agents.base.get_agent_model", return_value="test-model"):
            from aloha.agents.contact_research.agent import ContactResearchAgent
            return ContactResearchAgent()

    @pytest.fixture
    def base_context(self):
        return {
            "parcel_id": "TEST-001",
            "owner_id": 42,
            "state": "FL",
            "county": "miami-dade",
            "owner_name": "SMITH, JOHN",
            "location": "Miami, FL",
        }

    @pytest.mark.asyncio
    async def test_full_flow_with_verified_email(self, agent, base_context):
        agent._enrich_person = AsyncMock(return_value={
            "phone_numbers": [{"number": "3051234567", "type": "mobile"}],
            "emails": [{"address": "john@example.com"}],
        })
        agent._verify_email = AsyncMock(return_value={"status": "valid"})
        agent._persist = AsyncMock()

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        assert result["best_phone"] == "+13051234567"
        assert result["best_email"] == "john@example.com"
        assert result["email_verified"] is True
        assert result["quality"]["score"] == 10  # mobile + verified email
        agent._persist.assert_called_once()

    @pytest.mark.asyncio
    async def test_unverified_email(self, agent, base_context):
        agent._enrich_person = AsyncMock(return_value={
            "phone_numbers": [],
            "emails": [{"address": "john@example.com"}],
        })
        agent._verify_email = AsyncMock(return_value={"status": "invalid"})
        agent._persist = AsyncMock()

        result = await agent.run(base_context)

        assert result["email_verified"] is False
        assert result["quality"]["score"] == 3  # unverified email only

    @pytest.mark.asyncio
    async def test_no_enrichment_data(self, agent, base_context):
        agent._enrich_person = AsyncMock(return_value={})
        agent._persist = AsyncMock()

        result = await agent.run(base_context)

        assert result["best_phone"] is None
        assert result["best_email"] is None
        assert result["quality"]["score"] == 0

    @pytest.mark.asyncio
    async def test_no_owner_name_skips(self, agent, base_context):
        base_context.pop("owner_name")
        agent._load_owner = AsyncMock(return_value=(None, None))

        result = await agent.run(base_context)

        assert result["status"] == "skipped"
        assert "no owner name" in result["reason"]

    @pytest.mark.asyncio
    async def test_loads_owner_from_db_when_missing(self, agent, base_context):
        base_context.pop("owner_name")
        agent._load_owner = AsyncMock(return_value=("SMITH, JOHN", "Miami, FL"))
        agent._enrich_person = AsyncMock(return_value={})
        agent._persist = AsyncMock()

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        agent._load_owner.assert_called_once_with(42, "FL", "miami-dade")
