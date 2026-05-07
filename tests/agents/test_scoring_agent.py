"""Unit tests for the Scoring Agent (no DB, no LLM, no network).

Note: scoring *models* (score_lien_certificate, score_tax_deed) are tested
in test_scoring_models.py. This file covers the ScoringAgent.run() flow
and helper functions _model_to_dict and _pick_best_lien.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# conftest.py patches get_agent_model globally so these imports work.
from aloha.agents.scoring.agent import ScoringAgent, _model_to_dict, _pick_best_lien


# ═══════════════════════════════════════════════════════════════════════════════
# _model_to_dict
# ═══════════════════════════════════════════════════════════════════════════════


class TestModelToDict:
    def test_none(self):
        assert _model_to_dict(None) == {}

    def test_sqlalchemy_model(self):
        mock_obj = MagicMock()
        col1, col2 = MagicMock(), MagicMock()
        col1.name, col2.name = "id", "value"
        mock_obj.__table__ = MagicMock()
        mock_obj.__table__.columns = [col1, col2]
        mock_obj.id, mock_obj.value = 1, "test"
        assert _model_to_dict(mock_obj) == {"id": 1, "value": "test"}


# ═══════════════════════════════════════════════════════════════════════════════
# _pick_best_lien
# ═══════════════════════════════════════════════════════════════════════════════


class TestPickBestLien:
    def _make_lien(self, status="active", tax_year=2023):
        lien = MagicMock()
        lien.lien_status = status
        lien.tax_year = tax_year
        return lien

    def test_prefers_active(self):
        active = self._make_lien("active", 2022)
        inactive = self._make_lien("redeemed", 2023)
        result = _pick_best_lien([inactive, active])
        assert result.lien_status == "active"

    def test_latest_tax_year(self):
        older = self._make_lien("active", 2021)
        newer = self._make_lien("active", 2023)
        assert _pick_best_lien([older, newer]).tax_year == 2023

    def test_none_tax_year_sorted_last(self):
        with_year = self._make_lien("active", 2022)
        no_year = self._make_lien("active", None)
        assert _pick_best_lien([no_year, with_year]).tax_year == 2022

    def test_empty_list(self):
        assert _pick_best_lien([]) is None

    def test_none_input(self):
        assert _pick_best_lien(None) is None

    def test_single_lien(self):
        lien = self._make_lien("active", 2023)
        assert _pick_best_lien([lien]) is lien

    def test_all_inactive_falls_back(self):
        l1 = self._make_lien("redeemed", 2021)
        l2 = self._make_lien("expired", 2023)
        assert _pick_best_lien([l1, l2]).tax_year == 2023


# ═══════════════════════════════════════════════════════════════════════════════
# Agent integration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestScoringAgent:
    @pytest.fixture
    def agent(self):
        return ScoringAgent()

    @pytest.fixture
    def base_context(self):
        return {"parcel_id": "TEST-001", "state": "FL", "county": "orange"}

    @pytest.mark.asyncio
    async def test_lien_certificate_flow(self, agent, base_context):
        agent._load_data = AsyncMock(return_value=(
            {"parcel_id": "TEST-001", "assessed_total": 200000, "market_value_est": 250000},
            {
                "instrument_type": "lien_certificate", "lien_status": "active",
                "total_owed": 4200, "principal_amount": 3500,
                "certificate_interest_rate": 0.18, "tax_year": 2023,
                "years_delinquent": 2, "redemption_deadline": "2025-06-15",
            },
            {"owner_type": "individual", "is_absentee": True,
             "best_phone": "+15551234567", "best_email": "john@example.com"},
            None,  # no entity
        ))
        agent._persist = AsyncMock(return_value=1)

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        assert result["instrument_type"] == "lien_certificate"
        assert isinstance(result["overall_score"], (int, float))

    @pytest.mark.asyncio
    async def test_tax_deed_flow(self, agent, base_context):
        base_context["state"] = "TX"
        agent._load_data = AsyncMock(return_value=(
            {"parcel_id": "TEST-001", "assessed_total": 200000, "market_value_est": 250000},
            {"instrument_type": "tax_deed", "lien_status": "active",
             "total_owed": 15000, "opening_bid": 20000, "auction_date": "2025-06-15"},
            {"owner_type": "individual", "is_absentee": False},
            None,  # no entity
        ))
        agent._persist = AsyncMock(return_value=2)

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        assert result["instrument_type"] == "tax_deed"

    @pytest.mark.asyncio
    async def test_no_lien_skipped(self, agent, base_context):
        agent._load_data = AsyncMock(
            return_value=({"parcel_id": "TEST-001"}, {}, {}, None),
        )

        result = await agent.run(base_context)

        assert result["status"] == "skipped"
        assert result["reason"] == "no_lien_record"

    @pytest.mark.asyncio
    async def test_persist_called(self, agent, base_context):
        agent._load_data = AsyncMock(return_value=(
            {"parcel_id": "TEST-001", "assessed_total": 100000},
            {"instrument_type": "lien_certificate", "total_owed": 2000, "tax_year": 2023},
            {},
            None,  # no entity
        ))
        agent._persist = AsyncMock(return_value=3)

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        agent._persist.assert_called_once()

    @pytest.mark.asyncio
    async def test_entity_data_passed_to_lien_cert_model(self, agent, base_context):
        """When _load_data returns entity data, it flows to the lien cert model."""
        entity_dict = {
            "ucc_filings": [{"debtor": "Test LLC"}],
            "federal_tax_liens": [{"amount": 10_000}],
        }
        agent._load_data = AsyncMock(return_value=(
            {"parcel_id": "TEST-001", "assessed_total": 200000},
            {
                "instrument_type": "lien_certificate", "total_owed": 4000,
                "principal_amount": 3500, "certificate_interest_rate": 0.18,
            },
            {"owner_type": "llc", "is_absentee": False,
             "mailing_address": "123 St", "best_phone": None, "best_email": None},
            entity_dict,
        ))
        agent._persist = AsyncMock(return_value=10)

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        assert "entity_ucc_filings" in result["risk_flags"]
        assert "entity_tax_liens" in result["risk_flags"]

    @pytest.mark.asyncio
    async def test_entity_data_passed_to_tax_deed_model(self, agent, base_context):
        """When _load_data returns entity data, it flows to the tax deed model."""
        base_context["state"] = "TX"
        entity_dict = {
            "bankruptcy_history": [{"case": "Ch7"}],
            "litigation_summary": "Pending foreclosure",
        }
        agent._load_data = AsyncMock(return_value=(
            {"parcel_id": "TEST-001", "assessed_total": 200000,
             "market_value_est": 250000, "property_type": "residential"},
            {"instrument_type": "tax_deed", "opening_bid": 50000,
             "title_risk_level": "clear"},
            {"owner_type": "llc", "is_absentee": False},
            entity_dict,
        ))
        agent._persist = AsyncMock(return_value=11)

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        assert "entity_bankruptcy" in result["risk_flags"]
        assert "entity_active_litigation" in result["risk_flags"]
