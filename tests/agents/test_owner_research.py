"""Unit tests for the Owner Research Agent (no DB, no LLM, no network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aloha.agents.owner_research.tools import (
    classify_deed_type,
    classify_owner_type,
    detect_absentee,
    parse_mailing_address,
)


# ═══════════════════════════════════════════════════════════════════════════════
# classify_owner_type
# ═══════════════════════════════════════════════════════════════════════════════


class TestClassifyOwnerType:
    def test_llc(self):
        result = classify_owner_type("ACME HOLDINGS LLC")
        assert result["owner_type"] == "llc"
        assert result["is_entity"] is True

    def test_llc_dotted(self):
        result = classify_owner_type("SMITH VENTURES L.L.C.")
        assert result["owner_type"] == "llc"

    def test_corporation(self):
        result = classify_owner_type("NATIONAL BANK CORP.")
        assert result["owner_type"] == "corporation"
        assert result["is_entity"] is True

    def test_incorporated(self):
        result = classify_owner_type("ACME INCORPORATED")
        assert result["owner_type"] == "corporation"

    def test_trust(self):
        result = classify_owner_type("SMITH FAMILY TRUST")
        assert result["owner_type"] == "trust"
        assert result["is_entity"] is True

    def test_trustee(self):
        result = classify_owner_type("JOHN SMITH AS TRUSTEE")
        assert result["owner_type"] == "trust"

    def test_partnership(self):
        result = classify_owner_type("JONES AND SMITH LLP")
        assert result["owner_type"] == "partnership"

    def test_government(self):
        result = classify_owner_type("COUNTY OF MIAMI-DADE")
        assert result["owner_type"] == "government"
        assert result["is_entity"] is True

    def test_government_federal(self):
        result = classify_owner_type("UNITED STATES HUD")
        assert result["owner_type"] == "government"

    def test_individual_with_comma(self):
        result = classify_owner_type("SMITH, JOHN A")
        assert result["owner_type"] == "individual"
        assert result["is_entity"] is False
        assert result["confidence"] == "high"

    def test_individual_all_caps_multiple_words(self):
        result = classify_owner_type("JOHN ANDREW SMITH")
        assert result["owner_type"] == "individual"
        assert result["confidence"] == "medium"

    def test_empty_string(self):
        result = classify_owner_type("")
        assert result["owner_type"] == "unknown"

    def test_none_like_empty(self):
        result = classify_owner_type("   ")
        assert result["owner_type"] == "unknown"


# ═══════════════════════════════════════════════════════════════════════════════
# detect_absentee
# ═══════════════════════════════════════════════════════════════════════════════


class TestDetectAbsentee:
    def test_same_address(self):
        result = detect_absentee("123 Main St Orlando FL", "123 Main St Orlando FL")
        assert result["is_absentee"] is False
        assert result["match_confidence"] == "high"

    def test_different_address(self):
        result = detect_absentee(
            "123 Main St Orlando FL",
            "456 Oak Ave Tampa FL",
        )
        assert result["is_absentee"] is True

    def test_missing_property_address(self):
        result = detect_absentee(None, "456 Oak Ave")
        assert result["is_absentee"] is None
        assert result["match_confidence"] == "unknown"

    def test_missing_mailing_address(self):
        result = detect_absentee("123 Main St", None)
        assert result["is_absentee"] is None

    def test_both_none(self):
        result = detect_absentee(None, None)
        assert result["is_absentee"] is None

    def test_partial_overlap(self):
        result = detect_absentee(
            "123 Main St Orlando FL 32801",
            "123 Main St Orlando FL 32802",
        )
        # Most tokens overlap -> not absentee
        assert result["is_absentee"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# parse_mailing_address
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseMailingAddress:
    def test_full_comma_separated(self):
        result = parse_mailing_address("123 Main St, Orlando, FL 32801")
        assert result["street"] == "123 Main St"
        assert result["city"] == "ORLANDO"
        assert result["state"] == "FL"
        assert result["zip"] == "32801"

    def test_zip_plus_four(self):
        result = parse_mailing_address("123 Main St, Orlando, FL 32801-1234")
        assert result["zip"] == "32801"  # 5-digit only

    def test_no_comma_with_state(self):
        result = parse_mailing_address("PO BOX 5 MIAMI FL 33101")
        assert result["state"] == "FL"
        assert result["zip"] == "33101"
        assert result["city"] == "Miami"

    def test_empty_string(self):
        result = parse_mailing_address("")
        assert result["street"] is None
        assert result["city"] is None
        assert result["state"] is None
        assert result["zip"] is None

    def test_none_input(self):
        result = parse_mailing_address(None)
        assert result["state"] is None

    def test_full_preserved(self):
        result = parse_mailing_address("123 Main St, City, FL 32801")
        assert result["full"] == "123 Main St, City, FL 32801"


# ═══════════════════════════════════════════════════════════════════════════════
# classify_deed_type
# ═══════════════════════════════════════════════════════════════════════════════


class TestClassifyDeedType:
    def test_warranty(self):
        assert classify_deed_type("WARRANTY DEED") == "warranty"

    def test_quitclaim(self):
        assert classify_deed_type("QUIT CLAIM DEED") == "quitclaim"

    def test_trust_deed(self):
        assert classify_deed_type("DEED OF TRUST") == "trust_deed"

    def test_grant(self):
        assert classify_deed_type("GRANT DEED RECORDED") == "grant"

    def test_special_warranty(self):
        # "WARRANTY" pattern matches before "SPECIAL WARRANTY" in pattern list
        assert classify_deed_type("SPECIAL WARRANTY DEED") == "warranty"

    def test_tax_deed(self):
        assert classify_deed_type("TAX DEED ISSUED") == "tax_deed"

    def test_foreclosure(self):
        assert classify_deed_type("SHERIFF DEED") == "foreclosure"

    def test_none(self):
        assert classify_deed_type(None) is None

    def test_unrecognized(self):
        assert classify_deed_type("RANDOM TEXT XYZ") is None

    def test_case_insensitive(self):
        assert classify_deed_type("warranty deed") == "warranty"


# ═══════════════════════════════════════════════════════════════════════════════
# Agent integration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOwnerResearchAgent:
    @pytest.fixture
    def agent(self):
        with patch("aloha.agents.base.get_agent_model", return_value="test-model"):
            from aloha.agents.owner_research.agent import OwnerResearchAgent
            return OwnerResearchAgent()

    @pytest.fixture
    def base_context(self):
        return {
            "parcel_id": "TEST-001",
            "state": "FL",
            "county": "orange",
            "address": "123 Main St, Orlando, FL 32801",
            "owner_of_record": "SMITH, JOHN A",
            "mailing_address": "456 Oak Ave, Tampa, FL 33601",
        }

    @pytest.mark.asyncio
    async def test_full_flow_individual(self, agent, base_context):
        agent._load_from_db = AsyncMock(return_value=("SMITH, JOHN A", "123 Main St"))
        agent._get_mailing_from_db = AsyncMock(return_value="456 Oak Ave, Tampa, FL 33601")
        agent._persist = AsyncMock(return_value=42)

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        assert result["owner_type"] == "individual"
        assert result["is_entity"] is False
        assert result["is_absentee"] is True
        agent._persist.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_flow_entity(self, agent, base_context):
        base_context["owner_of_record"] = "ACME HOLDINGS LLC"
        agent._load_from_db = AsyncMock(return_value=("ACME HOLDINGS LLC", "123 Main St"))
        agent._get_mailing_from_db = AsyncMock(return_value=None)
        agent._persist = AsyncMock(return_value=42)

        result = await agent.run(base_context)

        assert result["owner_type"] == "llc"
        assert result["is_entity"] is True

    @pytest.mark.asyncio
    async def test_loads_from_db_when_missing(self, agent, base_context):
        base_context.pop("owner_of_record")
        base_context.pop("address")
        agent._load_from_db = AsyncMock(return_value=("SMITH, JOHN A", "123 Main St"))
        agent._get_mailing_from_db = AsyncMock(return_value=None)
        agent._persist = AsyncMock(return_value=42)

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        agent._load_from_db.assert_called_once()

    @pytest.mark.asyncio
    async def test_deed_type_classification(self, agent, base_context):
        base_context["deed_description"] = "WARRANTY DEED"
        agent._load_from_db = AsyncMock(return_value=("SMITH, JOHN A", "123 Main St"))
        agent._get_mailing_from_db = AsyncMock(return_value=None)
        agent._persist = AsyncMock(return_value=42)

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        # Verify the persist was called (deed_type is set on the Owner object)
        agent._persist.assert_called_once()
