"""Unit tests for the Discovery Agent (no DB, no LLM, no network)."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# conftest.py patches get_agent_model at module level so agent imports work.
from aloha.agents.discovery.agent import (
    DiscoveryAgent,
    _deadline_priority,
    _float_or_none,
    _hash,
)
from aloha.agents.discovery.state_registry import (
    InstrumentType,
    classify_instrument,
    get_state_info,
)


# ═══════════════════════════════════════════════════════════════════════════════
# _hash
# ═══════════════════════════════════════════════════════════════════════════════


class TestHash:
    def test_deterministic(self):
        d = {"a": 1, "b": 2}
        assert _hash(d) == _hash(d)

    def test_different_dicts(self):
        assert _hash({"a": 1}) != _hash({"b": 2})

    def test_key_order_irrelevant(self):
        assert _hash({"a": 1, "b": 2}) == _hash({"b": 2, "a": 1})

    def test_returns_hex_string(self):
        result = _hash({"x": 42})
        assert isinstance(result, str)
        assert len(result) == 32  # MD5 hex digest


# ═══════════════════════════════════════════════════════════════════════════════
# _float_or_none
# ═══════════════════════════════════════════════════════════════════════════════


class TestFloatOrNone:
    def test_none(self):
        assert _float_or_none(None) is None

    def test_valid_int(self):
        assert _float_or_none(42) == 42.0

    def test_valid_str(self):
        assert _float_or_none("3.14") == 3.14

    def test_invalid_str(self):
        assert _float_or_none("not_a_number") is None

    def test_empty_str(self):
        assert _float_or_none("") is None

    def test_float_passthrough(self):
        assert _float_or_none(2.5) == 2.5


# ═══════════════════════════════════════════════════════════════════════════════
# _deadline_priority
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeadlinePriority:
    def test_no_deadline(self):
        assert _deadline_priority({}) == 5

    def test_urgent_redemption(self):
        soon = (date.today() + timedelta(days=10)).isoformat()
        assert _deadline_priority({"redemption_deadline": soon}) == 1

    def test_medium_priority(self):
        mid = (date.today() + timedelta(days=60)).isoformat()
        assert _deadline_priority({"redemption_deadline": mid}) == 2

    def test_low_priority(self):
        far = (date.today() + timedelta(days=180)).isoformat()
        assert _deadline_priority({"auction_date": far}) == 5

    def test_past_deadline(self):
        past = (date.today() - timedelta(days=10)).isoformat()
        assert _deadline_priority({"redemption_deadline": past}) == 1

    def test_invalid_date(self):
        assert _deadline_priority({"redemption_deadline": "not-a-date"}) == 5

    def test_date_object(self):
        soon = date.today() + timedelta(days=5)
        assert _deadline_priority({"auction_date": soon}) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# _guess_assessor_url
# ═══════════════════════════════════════════════════════════════════════════════


class TestGuessAssessorUrl:
    @pytest.fixture
    def agent(self):
        return DiscoveryAgent()

    def test_url_format(self, agent):
        url = agent._guess_assessor_url("FL", "orange")
        assert url == "https://www.orangecountyfl.gov/propertytax"

    def test_multi_word_county(self, agent):
        url = agent._guess_assessor_url("CA", "Los Angeles")
        assert url == "https://www.losangelescountyca.gov/propertytax"

    def test_case_handling(self, agent):
        url = agent._guess_assessor_url("TX", "HARRIS")
        assert "harris" in url


# ═══════════════════════════════════════════════════════════════════════════════
# State Registry
# ═══════════════════════════════════════════════════════════════════════════════


class TestStateRegistry:
    def test_get_state_info_fl(self):
        info = get_state_info("FL")
        assert info is not None
        assert info.instrument == InstrumentType.LIEN_CERT
        assert info.cert_rate_cap == 0.18

    def test_get_state_info_tx(self):
        info = get_state_info("TX")
        assert info is not None
        assert info.instrument == InstrumentType.TAX_DEED

    def test_get_state_info_case_insensitive(self):
        assert get_state_info("fl") == get_state_info("FL")

    def test_get_state_info_unknown(self):
        assert get_state_info("XX") is None

    def test_classify_instrument_fl(self):
        assert classify_instrument("FL") == InstrumentType.LIEN_CERT

    def test_classify_instrument_tx(self):
        assert classify_instrument("TX") == InstrumentType.TAX_DEED

    def test_classify_instrument_oh_hybrid(self):
        assert classify_instrument("OH") == InstrumentType.HYBRID

    def test_classify_instrument_unknown_defaults_hybrid(self):
        assert classify_instrument("XX") == InstrumentType.HYBRID


# ═══════════════════════════════════════════════════════════════════════════════
# Agent integration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDiscoveryAgent:
    @pytest.fixture
    def agent(self):
        return DiscoveryAgent()

    @pytest.fixture
    def base_context(self):
        return {"state": "FL", "county": "orange"}

    @pytest.mark.asyncio
    async def test_no_records_found(self, agent, base_context):
        agent._scrape = AsyncMock(return_value=[])

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        assert result["records_found"] == 0
        assert result["enqueued"] == 0

    @pytest.mark.asyncio
    async def test_records_found_and_enqueued(self, agent, base_context):
        agent._scrape = AsyncMock(return_value=[
            {"parcel_id": "P1", "address": "123 Main St"},
            {"parcel_id": "P2", "address": "456 Oak Ave"},
        ])
        agent._persist_and_enqueue = AsyncMock(return_value=2)

        result = await agent.run(base_context)

        assert result["status"] == "complete"
        assert result["records_found"] == 2
        assert result["enqueued"] == 2
        assert result["instrument"] == "lien_certificate"

    @pytest.mark.asyncio
    async def test_instrument_mismatch_skipped(self, agent, base_context):
        base_context["instrument_filter"] = "tax_deed"

        result = await agent.run(base_context)

        assert result["status"] == "skipped"
        assert result["reason"] == "instrument_mismatch"

    @pytest.mark.asyncio
    async def test_hybrid_state_allows_any_filter(self, agent, base_context):
        base_context["state"] = "OH"
        base_context["instrument_filter"] = "tax_deed"
        agent._scrape = AsyncMock(return_value=[])

        result = await agent.run(base_context)

        assert result["status"] == "complete"

    @pytest.mark.asyncio
    async def test_state_uppercased(self, agent, base_context):
        base_context["state"] = "fl"
        agent._scrape = AsyncMock(return_value=[])

        result = await agent.run(base_context)

        assert result["status"] == "complete"
