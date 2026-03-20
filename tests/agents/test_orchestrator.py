"""Unit tests for the Orchestrator Agent (no DB, no LLM, no network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# conftest.py patches get_agent_model at module level so agent imports work.
from aloha.agents.orchestrator.agent import OrchestratorAgent


# ═══════════════════════════════════════════════════════════════════════════════
# OrchestratorAgent.run (single-dispatch mode)
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrchestratorRun:
    @pytest.fixture
    def agent(self):
        return OrchestratorAgent()

    @pytest.mark.asyncio
    async def test_dispatch_known_agent(self, agent):
        mock_sub = AsyncMock()
        mock_sub.run = AsyncMock(return_value={"status": "complete"})
        agent._dispatch_map = {"scoring": mock_sub}

        result = await agent.run({
            "item_id": 1,
            "agent_name": "scoring",
            "payload": {"parcel_id": "TEST-001"},
        })

        assert result["status"] == "complete"
        mock_sub.run.assert_called_once_with({"parcel_id": "TEST-001"})

    @pytest.mark.asyncio
    async def test_dispatch_unknown_agent(self, agent):
        agent._dispatch_map = {}

        result = await agent.run({
            "item_id": 1,
            "agent_name": "nonexistent",
            "payload": {},
        })

        assert result["status"] == "error"
        assert "nonexistent" in result["reason"]


# ═══════════════════════════════════════════════════════════════════════════════
# _get_agent
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetAgent:
    @pytest.fixture
    def agent(self):
        return OrchestratorAgent()

    def test_returns_agent_from_map(self, agent):
        mock_sub = MagicMock()
        agent._dispatch_map = {"report": mock_sub}
        assert agent._get_agent("report") is mock_sub

    def test_returns_none_for_unknown(self, agent):
        agent._dispatch_map = {"report": MagicMock()}
        assert agent._get_agent("unknown") is None

    def test_lazy_builds_map(self, agent):
        # Map is empty initially → _get_agent triggers _build_dispatch_map
        agent._build_dispatch_map = MagicMock()
        agent._get_agent("scoring")
        agent._build_dispatch_map.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# _process_one
# ═══════════════════════════════════════════════════════════════════════════════


class TestProcessOne:
    @pytest.fixture
    def agent(self):
        return OrchestratorAgent()

    @pytest.mark.asyncio
    async def test_empty_queue(self, agent):
        mock_session = AsyncMock()
        mock_queue_repo = MagicMock()
        mock_queue_repo.claim_one = AsyncMock(return_value=None)

        with patch("aloha.agents.orchestrator.agent.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("aloha.agents.orchestrator.agent.QueueRepository", return_value=mock_queue_repo):
                result = await agent._process_one()

        assert result is False

    @pytest.mark.asyncio
    async def test_dispatches_and_completes(self, agent):
        # Create a mock queue item
        mock_item = MagicMock()
        mock_item.id = 42
        mock_item.agent_name = "scoring"
        mock_item.payload = {"parcel_id": "TEST-001"}

        mock_queue_repo = MagicMock()
        mock_queue_repo.claim_one = AsyncMock(return_value=mock_item)
        mock_queue_repo.complete = AsyncMock()

        mock_session = AsyncMock()

        mock_sub = AsyncMock()
        mock_sub.run = AsyncMock(return_value={"status": "complete"})
        agent._dispatch_map = {"scoring": mock_sub}

        with patch("aloha.agents.orchestrator.agent.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("aloha.agents.orchestrator.agent.QueueRepository", return_value=mock_queue_repo):
                result = await agent._process_one()

        assert result is True


# ═══════════════════════════════════════════════════════════════════════════════
# stop
# ═══════════════════════════════════════════════════════════════════════════════


class TestStop:
    def test_stop_sets_flag(self):
        agent = OrchestratorAgent()
        agent._running = True
        agent.stop()
        assert agent._running is False

    def test_initial_state(self):
        agent = OrchestratorAgent()
        assert agent._running is False
