"""Unit tests for the Entity Research Agent (no DB, no LLM, no network)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

# conftest.py patches get_agent_model globally so these imports work.
from aloha.agents.entity_research.agent import EntityResearchAgent, _is_commercial_ra


# ═══════════════════════════════════════════════════════════════════════════════
# Pure function tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsCommercialRA:
    def test_ct_corporation(self):
        assert _is_commercial_ra("CT CORPORATION SYSTEM") is True

    def test_northwest(self):
        assert _is_commercial_ra("NORTHWEST REGISTERED AGENT LLC") is True

    def test_legalzoom(self):
        assert _is_commercial_ra("LEGALZOOM.COM INC") is True

    def test_csc(self):
        assert _is_commercial_ra("CORPORATION SERVICE COMPANY") is True

    def test_harbor_compliance(self):
        assert _is_commercial_ra("HARBOR COMPLIANCE LLC") is True

    def test_individual_name(self):
        assert _is_commercial_ra("JOHN SMITH") is False

    def test_none(self):
        assert _is_commercial_ra(None) is False

    def test_empty(self):
        assert _is_commercial_ra("") is False

    def test_case_insensitive(self):
        assert _is_commercial_ra("ct corporation system") is True

    def test_partial_match(self):
        assert _is_commercial_ra("COGENCY GLOBAL INC") is True


class TestExtractBeneficialOwner:
    @pytest.fixture
    def agent(self):
        return EntityResearchAgent()

    def test_officer_found(self, agent):
        sos = {"officers": [{"name": "JOHN SMITH", "title": "President"}]}
        name, confidence = agent._extract_beneficial_owner(sos)
        assert name == "John Smith"
        assert confidence == "high"

    def test_manager_found(self, agent):
        sos = {"managers_members": [{"name": "JANE DOE", "title": "Manager"}]}
        name, confidence = agent._extract_beneficial_owner(sos)
        assert name == "Jane Doe"
        assert confidence == "high"

    def test_commercial_ra_officer_skipped(self, agent):
        sos = {
            "officers": [{"name": "CT CORPORATION SYSTEM", "title": "Agent"}],
            "registered_agent": "CT CORPORATION SYSTEM",
            "entity_name": "ACME LLC",
        }
        name, confidence = agent._extract_beneficial_owner(sos)
        assert name is None
        assert confidence == "low"

    def test_non_commercial_ra(self, agent):
        sos = {"registered_agent": "JOHN SMITH"}
        name, confidence = agent._extract_beneficial_owner(sos)
        assert name == "John Smith"
        assert confidence == "medium"

    def test_empty_result(self, agent):
        name, confidence = agent._extract_beneficial_owner({})
        assert name is None
        assert confidence == "unknown"

    def test_officers_before_managers(self, agent):
        sos = {
            "officers": [{"name": "ALICE", "title": "CEO"}],
            "managers_members": [{"name": "BOB", "title": "Manager"}],
        }
        name, _ = agent._extract_beneficial_owner(sos)
        assert name == "Alice"

    def test_empty_officer_name_skipped(self, agent):
        sos = {
            "officers": [{"name": "", "title": "CEO"}],
            "managers_members": [{"name": "BOB", "title": "Manager"}],
        }
        name, _ = agent._extract_beneficial_owner(sos)
        assert name == "Bob"


# ═══════════════════════════════════════════════════════════════════════════════
# Agent integration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEntityResearchAgent:
    @pytest.fixture
    def agent(self):
        return EntityResearchAgent()

    @pytest.fixture
    def base_context(self):
        return {
            "parcel_id": "TEST-001",
            "owner_id": 42,
            "entity_name": "ACME HOLDINGS LLC",
            "state": "FL",
            "county": "orange",
        }

    @pytest.mark.asyncio
    async def test_full_flow_with_sos_data(self, agent, base_context):
        agent._sos_lookup = AsyncMock(return_value={
            "entity_name": "ACME HOLDINGS LLC",
            "entity_type": "LLC",
            "status": "Active",
            "officers": [{"name": "JOHN SMITH", "title": "Manager"}],
            "registered_agent": "JOHN SMITH",
            "_search_state": "FL",
        })
        agent._find_related_entities = AsyncMock(return_value=["ENT-002", "ENT-003"])
        agent._persist = AsyncMock(return_value=99)

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        assert result["beneficial_owner"] == "John Smith"
        assert result["confidence"] == "high"
        assert result["entity_id"] == 99

    @pytest.mark.asyncio
    async def test_sos_unavailable(self, agent, base_context):
        agent._sos_lookup = AsyncMock(return_value={})
        agent._find_related_entities = AsyncMock(return_value=[])
        agent._persist = AsyncMock(return_value=99)

        result = await agent.run(base_context)

        assert result["beneficial_owner"] is None
        assert result["confidence"] == "unknown"

    @pytest.mark.asyncio
    async def test_commercial_ra_no_beneficial_owner(self, agent, base_context):
        agent._sos_lookup = AsyncMock(return_value={
            "entity_name": "ACME LLC",
            "officers": [{"name": "CT CORPORATION SYSTEM", "title": "Agent"}],
            "registered_agent": "CT CORPORATION SYSTEM",
        })
        agent._find_related_entities = AsyncMock(return_value=[])
        agent._persist = AsyncMock(return_value=99)

        result = await agent.run(base_context)

        assert result["beneficial_owner"] is None
        assert result["confidence"] == "low"
