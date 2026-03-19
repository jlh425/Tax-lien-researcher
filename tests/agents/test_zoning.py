"""Unit tests for the Zoning Agent (no DB, no LLM, no network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aloha.agents.zoning.tools import (
    assess_development_potential,
    classify_land_use,
    classify_zoning,
    summarise_zoning,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Tests — pure functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestClassifyZoning:
    def test_residential_single(self):
        result = classify_zoning("RS-1")
        assert result["category"] == "residential_single"
        assert result["is_residential"] is True
        assert result["density_indicator"] == "1"

    def test_commercial(self):
        result = classify_zoning("C-2")
        assert result["category"] == "commercial"
        assert result["is_residential"] is False

    def test_industrial(self):
        result = classify_zoning("I-3")
        assert result["category"] == "industrial"

    def test_mixed_use(self):
        result = classify_zoning("MU")
        assert result["category"] == "mixed_use"

    def test_agricultural(self):
        result = classify_zoning("AG")
        assert result["category"] == "agricultural"

    def test_planned_unit_development(self):
        result = classify_zoning("PUD")
        assert result["category"] == "planned_unit_development"

    def test_residential_multi(self):
        result = classify_zoning("RM-4")
        assert result["category"] == "residential_multi"
        assert result["is_residential"] is True

    def test_unknown_code(self):
        result = classify_zoning("XYZ-99")
        assert result["category"] == "unknown"
        assert result["code"] == "XYZ-99"

    def test_none_code(self):
        result = classify_zoning(None)
        assert result["code"] is None
        assert result["category"] == "unknown"
        assert result["is_residential"] is False

    def test_empty_string(self):
        result = classify_zoning("")
        assert result["code"] is None
        assert result["category"] == "unknown"

    def test_lowercase_normalised(self):
        result = classify_zoning("r-1")
        assert result["code"] == "R-1"
        assert result["category"] == "residential"

    def test_business_district(self):
        result = classify_zoning("B-1")
        assert result["category"] == "commercial"

    def test_manufacturing(self):
        result = classify_zoning("M-2")
        assert result["category"] == "industrial"


class TestClassifyLandUse:
    def test_residential(self):
        result = classify_land_use("0100")
        assert result["property_type"] == "residential"

    def test_vacant_land(self):
        result = classify_land_use("1000")
        assert result["property_type"] == "vacant_land"

    def test_commercial(self):
        result = classify_land_use("2100")
        assert result["property_type"] == "commercial"

    def test_industrial(self):
        result = classify_land_use("3000")
        assert result["property_type"] == "industrial"

    def test_agricultural(self):
        result = classify_land_use("5000")
        assert result["property_type"] == "agricultural"

    def test_government(self):
        result = classify_land_use("7000")
        assert result["property_type"] == "government"

    def test_unknown_code(self):
        result = classify_land_use("9999")
        assert result["property_type"] == "other"

    def test_none(self):
        result = classify_land_use(None)
        assert result["property_type"] == "unknown"

    def test_whitespace_stripped(self):
        result = classify_land_use("  0100  ")
        assert result["property_type"] == "residential"


class TestAssessDevelopmentPotential:
    def test_high_potential_vacant_large(self):
        result = assess_development_potential(
            zoning_category="agricultural",
            acreage=10.0,
            year_built=None,
        )
        assert result["potential"] == "high"
        assert result["score"] >= 4

    def test_medium_potential(self):
        result = assess_development_potential(
            zoning_category="commercial",
            acreage=2.0,
        )
        assert result["potential"] == "medium"

    def test_low_potential(self):
        result = assess_development_potential(
            zoning_category="residential",
            acreage=0.25,
            year_built=1960,
        )
        assert result["potential"] == "low"

    def test_no_potential(self):
        result = assess_development_potential(
            zoning_category="residential",
            acreage=0.1,
        )
        assert result["potential"] == "none"

    def test_old_structure_adds_factor(self):
        result = assess_development_potential(
            zoning_category="commercial",
            year_built=1950,
        )
        assert any("aging" in f for f in result["factors"])

    def test_mixed_use_bonus(self):
        result = assess_development_potential(
            zoning_category="mixed_use",
            acreage=2.0,
        )
        assert any("mixed_use" in f for f in result["factors"])

    def test_score_capped_at_5(self):
        result = assess_development_potential(
            zoning_category="agricultural",
            acreage=20.0,
            year_built=1940,
        )
        assert result["score"] <= 5


class TestSummariseZoning:
    def test_combined_summary(self):
        zoning = {"code": "R-1", "category": "residential", "description": "Residential", "is_residential": True}
        land_use = {"property_type": "residential", "description": "Residential property"}
        development = {"potential": "low", "score": 1, "factors": ["aging structure"]}

        result = summarise_zoning(zoning=zoning, land_use=land_use, development=development)

        assert result["zoning_code"] == "R-1"
        assert result["zoning_category"] == "residential"
        assert result["is_residential"] is True
        assert result["land_use_type"] == "residential"
        assert result["development_potential"] == "low"
        assert result["development_score"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Agent Tests — mocked DB
# ═══════════════════════════════════════════════════════════════════════════════


class TestZoningAgent:
    @pytest.fixture
    def agent(self):
        with patch("aloha.agents.base.get_agent_model", return_value="test-model"):
            from aloha.agents.zoning.agent import ZoningAgent
            return ZoningAgent()

    @pytest.fixture
    def base_context(self):
        return {
            "parcel_id": "TEST-001",
            "state": "FL",
            "county": "miami-dade",
            "zoning_code": "RS-1",
            "land_use_code": "0100",
            "acreage": 0.25,
            "year_built": 2005,
            "assessed_total": 200000,
            "market_value_est": 250000,
        }

    @pytest.mark.asyncio
    async def test_full_flow(self, agent, base_context):
        agent._load_parcel = AsyncMock(return_value={})
        agent._persist = AsyncMock()

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        assert result["zoning_category"] == "residential_single"
        assert result["is_residential"] is True
        assert result["land_use_type"] == "residential"
        assert result["development_potential"] in ("none", "low", "medium", "high")
        agent._persist.assert_called_once()

    @pytest.mark.asyncio
    async def test_loads_from_db_when_context_empty(self, agent):
        context = {
            "parcel_id": "TEST-002",
            "state": "FL",
            "county": "miami-dade",
        }
        agent._load_parcel = AsyncMock(return_value={
            "zoning": "C-2",
            "land_use_code": "2100",
            "acreage": 5.0,
            "year_built": 1960,
            "assessed_total": 500000,
            "market_value_est": 800000,
        })
        agent._persist = AsyncMock()

        result = await agent.run(context)

        assert result["status"] == "complete"
        assert result["zoning_category"] == "commercial"
        agent._load_parcel.assert_called_once_with("TEST-002")

    @pytest.mark.asyncio
    async def test_no_zoning_data(self, agent):
        context = {
            "parcel_id": "TEST-003",
            "state": "FL",
            "county": "miami-dade",
        }
        agent._load_parcel = AsyncMock(return_value={})
        agent._persist = AsyncMock()

        result = await agent.run(context)

        assert result["status"] == "complete"
        assert result["zoning_category"] == "unknown"

    @pytest.mark.asyncio
    async def test_agricultural_high_development(self, agent, base_context):
        base_context["zoning_code"] = "AG"
        base_context["acreage"] = 15.0
        base_context["year_built"] = None
        agent._load_parcel = AsyncMock(return_value={})
        agent._persist = AsyncMock()

        result = await agent.run(base_context)

        assert result["zoning_category"] == "agricultural"
        assert result["development_potential"] == "high"

    @pytest.mark.asyncio
    async def test_persist_called_with_correct_args(self, agent, base_context):
        agent._load_parcel = AsyncMock(return_value={})
        agent._persist = AsyncMock()

        await agent.run(base_context)

        call_kwargs = agent._persist.call_args.kwargs
        assert call_kwargs["parcel_id"] == "TEST-001"
        assert call_kwargs["zoning_code"] == "RS-1"
        assert call_kwargs["state"] == "FL"
        assert call_kwargs["county"] == "miami-dade"
