"""Unit tests for the Report Agent (no DB, no LLM, no network)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

# conftest.py patches get_agent_model globally so these imports work.
from aloha.agents.report.agent import (
    ReportAgent,
    _extract_condition_summary,
    _fallback_narrative,
    _obj_to_dict,
)


# ═══════════════════════════════════════════════════════════════════════════════
# _extract_condition_summary
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractConditionSummary:
    def test_valid_json_with_summary(self):
        content = json.dumps({"summary": "Vacant lot with overgrown vegetation"})
        assert _extract_condition_summary(content) == "Vacant lot with overgrown vegetation"

    def test_valid_json_no_summary(self):
        content = json.dumps({"confidence": 0.5})
        # No "summary" key → falls through to content[:200]
        assert _extract_condition_summary(content) == content

    def test_invalid_json(self):
        result = _extract_condition_summary("not json at all")
        assert result == "not json at all"

    def test_empty_string(self):
        assert _extract_condition_summary("") == ""

    def test_long_content_truncated(self):
        content = "x" * 500
        result = _extract_condition_summary(content)
        assert len(result) == 200


# ═══════════════════════════════════════════════════════════════════════════════
# _obj_to_dict
# ═══════════════════════════════════════════════════════════════════════════════


class TestObjToDict:
    def test_none(self):
        assert _obj_to_dict(None) == {}

    def test_dict_passthrough(self):
        assert _obj_to_dict({"a": 1}) == {"a": 1}

    def test_sqlalchemy_model(self):
        mock_obj = MagicMock()
        col1, col2 = MagicMock(), MagicMock()
        col1.name, col2.name = "id", "name"
        mock_obj.__table__ = MagicMock()
        mock_obj.__table__.columns = [col1, col2]
        mock_obj.id, mock_obj.name = 42, "test"
        assert _obj_to_dict(mock_obj) == {"id": 42, "name": "test"}


# ═══════════════════════════════════════════════════════════════════════════════
# _fallback_narrative
# ═══════════════════════════════════════════════════════════════════════════════


class TestFallbackNarrative:
    @pytest.fixture
    def full_report(self):
        return {
            "parcel_id": "TEST-001",
            "instrument_type": "lien_certificate",
            "recommended_action": "high_priority_buy",
            "property": {"address": "123 Main St"},
            "lien": {"total_owed": 4200.50},
            "score": {"overall_score": 82, "risk_flags": ["high_lien_to_value", "redemption_urgent"]},
            "owner": {"owner_of_record": "SMITH, JOHN", "owner_type": "individual", "is_absentee": True},
        }

    def test_full_data(self, full_report):
        result = _fallback_narrative({}, full_report)
        assert "TEST-001" in result
        assert "123 Main St" in result
        assert "82" in result
        assert "SMITH, JOHN" in result
        assert "4,200.50" in result

    def test_missing_fields(self):
        report = {
            "parcel_id": "X", "instrument_type": "tax_deed", "recommended_action": "pass",
            "property": {}, "lien": {},
            "score": {"overall_score": None, "risk_flags": []}, "owner": {},
        }
        result = _fallback_narrative({}, report)
        assert "N/A" in result
        assert "Unknown" in result

    def test_risk_flags_joined(self, full_report):
        result = _fallback_narrative({}, full_report)
        assert "high_lien_to_value" in result

    def test_no_total_owed_omitted(self):
        report = {
            "parcel_id": "X", "instrument_type": "lien_certificate", "recommended_action": "monitor",
            "property": {"address": "123 St"}, "lien": {},
            "score": {"overall_score": 50, "risk_flags": []}, "owner": {"owner_of_record": "DOE"},
        }
        result = _fallback_narrative({}, report)
        assert "Amount Owed" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# _compile_report
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompileReport:
    @pytest.fixture
    def agent(self):
        return ReportAgent()

    @pytest.fixture
    def full_data(self):
        return {
            "parcel": {
                "parcel_id": "TEST-001", "address": "123 Main St", "property_type": "residential",
                "zoning": "RS-1", "acreage": 0.25, "year_built": 2005,
                "assessed_total": 200000, "market_value_est": 250000,
            },
            "liens": [{
                "instrument_type": "lien_certificate", "lien_status": "active", "tax_year": 2023,
                "principal_amount": 3500, "total_owed": 4200, "certificate_interest_rate": 0.18,
                "redemption_deadline": "2024-06-15", "auction_date": None, "auction_platform": None,
                "opening_bid": None, "source_url": "https://example.com",
            }],
            "owners": [{
                "owner_of_record": "SMITH, JOHN", "owner_type": "individual", "is_absentee": True,
                "mailing_address": "456 Oak", "beneficial_owner": None,
                "beneficial_owner_confidence": None, "best_phone": "+15551234567",
                "best_email": "john@example.com",
            }],
            "score": {
                "overall_score": 82, "instrument_type": "lien_certificate",
                "score_model_version": "v1", "risk_flags": ["high_lien_to_value"],
                "score_rationale": "Good investment", "property_potential": 70, "risk_score": 20,
            },
        }

    def test_high_score_buy(self, agent, full_data):
        assert agent._compile_report(full_data, "FL", "orange")["recommended_action"] == "high_priority_buy"

    def test_medium_score_research(self, agent, full_data):
        full_data["score"]["overall_score"] = 60
        assert agent._compile_report(full_data, "FL", "orange")["recommended_action"] == "research_further"

    def test_low_score_monitor(self, agent, full_data):
        full_data["score"]["overall_score"] = 40
        assert agent._compile_report(full_data, "FL", "orange")["recommended_action"] == "monitor"

    def test_very_low_score_pass(self, agent, full_data):
        full_data["score"]["overall_score"] = 20
        assert agent._compile_report(full_data, "FL", "orange")["recommended_action"] == "pass"

    def test_no_score_pending(self, agent, full_data):
        full_data["score"]["overall_score"] = None
        assert agent._compile_report(full_data, "FL", "orange")["recommended_action"] == "pending_scoring"

    def test_property_section(self, agent, full_data):
        report = agent._compile_report(full_data, "FL", "orange")
        assert report["property"]["address"] == "123 Main St"
        assert report["property"]["property_type"] == "residential"

    def test_no_liens(self, agent, full_data):
        full_data["liens"] = []
        assert agent._compile_report(full_data, "FL", "orange")["lien"]["instrument_type"] is None

    def test_no_owners(self, agent, full_data):
        full_data["owners"] = []
        assert agent._compile_report(full_data, "FL", "orange")["owner"]["owner_of_record"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# Agent integration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestReportAgent:
    @pytest.fixture
    def agent(self):
        return ReportAgent()

    @pytest.fixture
    def base_context(self):
        return {"parcel_id": "TEST-001", "state": "FL", "county": "orange"}

    @pytest.mark.asyncio
    async def test_full_flow(self, agent, base_context):
        agent._load_all_data = AsyncMock(return_value={
            "parcel": {"parcel_id": "TEST-001", "address": "123 Main St"},
            "liens": [{"instrument_type": "lien_certificate", "total_owed": 4200}],
            "owners": [{"owner_of_record": "SMITH"}],
            "score": {"overall_score": 82},
            "property_condition": None,
        })
        agent._generate_narrative = AsyncMock(return_value="Great investment opportunity.")
        agent._complete_parcel = AsyncMock()

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        assert result["report"]["recommended_action"] == "high_priority_buy"
        assert result["report"]["narrative"] == "Great investment opportunity."

    @pytest.mark.asyncio
    async def test_parcel_not_found(self, agent, base_context):
        agent._load_all_data = AsyncMock(return_value={
            "parcel": {}, "liens": [], "owners": [], "score": {}, "property_condition": None,
        })

        result = await agent.run(base_context)

        assert result["status"] == "failed"
        assert result["reason"] == "parcel_not_found"

    @pytest.mark.asyncio
    async def test_narrative_fallback(self, agent, base_context):
        agent._load_all_data = AsyncMock(return_value={
            "parcel": {"parcel_id": "TEST-001"},
            "liens": [], "owners": [],
            "score": {"overall_score": None},
            "property_condition": None,
        })
        agent._generate_narrative = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        agent._complete_parcel = AsyncMock()

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        assert "INVESTMENT MEMO" in result["report"]["narrative"]
