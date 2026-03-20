"""Unit tests for the Database Agent (no DB, no LLM, no network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# conftest.py patches get_agent_model at module level so agent imports work.
from aloha.agents.database.agent import DatabaseAgent


# ═══════════════════════════════════════════════════════════════════════════════
# DatabaseAgent.run — task dispatcher
# ═══════════════════════════════════════════════════════════════════════════════


class TestDatabaseAgentRun:
    @pytest.fixture
    def agent(self):
        return DatabaseAgent()

    @pytest.mark.asyncio
    async def test_refresh_stale(self, agent):
        agent.refresh_stale_parcels = AsyncMock(return_value=5)

        result = await agent.run({"task": "refresh_stale"})

        assert result["status"] == "complete"
        assert result["task"] == "refresh_stale"
        assert result["count"] == 5
        agent.refresh_stale_parcels.assert_called_once()

    @pytest.mark.asyncio
    async def test_discovery(self, agent):
        agent.scheduled_discovery = AsyncMock(return_value=10)

        result = await agent.run({"task": "discovery"})

        assert result["status"] == "complete"
        assert result["task"] == "discovery"
        assert result["count"] == 10

    @pytest.mark.asyncio
    async def test_cleanup(self, agent):
        agent.cleanup_complete_queue = AsyncMock(return_value=3)

        result = await agent.run({"task": "cleanup"})

        assert result["status"] == "complete"
        assert result["task"] == "cleanup"
        assert result["count"] == 3

    @pytest.mark.asyncio
    async def test_reset_stalled(self, agent):
        agent.reset_stalled_items = AsyncMock(return_value=2)

        result = await agent.run({"task": "reset_stalled"})

        assert result["status"] == "complete"
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_unknown_task(self, agent):
        result = await agent.run({"task": "bogus"})

        assert result["status"] == "error"
        assert "bogus" in result["reason"]

    @pytest.mark.asyncio
    async def test_default_task(self, agent):
        agent.refresh_stale_parcels = AsyncMock(return_value=0)

        result = await agent.run({})

        assert result["task"] == "refresh_stale"
        agent.refresh_stale_parcels.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# refresh_stale_parcels
# ═══════════════════════════════════════════════════════════════════════════════


class TestRefreshStaleParcels:
    @pytest.fixture
    def agent(self):
        return DatabaseAgent()

    @pytest.mark.asyncio
    async def test_marks_and_enqueues(self, agent):
        mock_parcel = MagicMock()
        mock_parcel.parcel_id = "P-001"
        mock_parcel.state = "FL"
        mock_parcel.county = "orange"
        mock_parcel.address = "123 Main St"

        mock_parcel_repo = MagicMock()
        mock_parcel_repo.mark_stale = AsyncMock(return_value=[mock_parcel])

        mock_queue_repo = MagicMock()
        mock_queue_repo.enqueue = AsyncMock()

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch("aloha.agents.database.agent.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            # Deferred imports inside the method — patch at the source module
            with patch("aloha.db.repositories.ParcelRepository", return_value=mock_parcel_repo):
                with patch("aloha.db.repositories.QueueRepository", return_value=mock_queue_repo):
                    count = await agent.refresh_stale_parcels()

        assert count == 1
        mock_queue_repo.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_stale_parcels(self, agent):
        mock_parcel_repo = MagicMock()
        mock_parcel_repo.mark_stale = AsyncMock(return_value=[])

        mock_queue_repo = MagicMock()
        mock_queue_repo.enqueue = AsyncMock()

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch("aloha.agents.database.agent.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("aloha.db.repositories.ParcelRepository", return_value=mock_parcel_repo):
                with patch("aloha.db.repositories.QueueRepository", return_value=mock_queue_repo):
                    count = await agent.refresh_stale_parcels()

        assert count == 0
        mock_queue_repo.enqueue.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# reset_stalled_items
# ═══════════════════════════════════════════════════════════════════════════════


class TestResetStalledItems:
    @pytest.fixture
    def agent(self):
        return DatabaseAgent()

    @pytest.mark.asyncio
    async def test_resets_items(self, agent):
        mock_queue_repo = MagicMock()
        mock_queue_repo.reset_stalled = AsyncMock(return_value=3)

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch("aloha.agents.database.agent.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("aloha.db.repositories.QueueRepository", return_value=mock_queue_repo):
                count = await agent.reset_stalled_items()

        assert count == 3

    @pytest.mark.asyncio
    async def test_none_returns_zero(self, agent):
        mock_queue_repo = MagicMock()
        mock_queue_repo.reset_stalled = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch("aloha.agents.database.agent.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("aloha.db.repositories.QueueRepository", return_value=mock_queue_repo):
                count = await agent.reset_stalled_items()

        assert count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Scheduler lifecycle
# ═══════════════════════════════════════════════════════════════════════════════


class TestScheduler:
    @pytest.mark.asyncio
    async def test_start_creates_scheduler(self):
        agent = DatabaseAgent()
        assert agent._scheduler is None

        agent.start_scheduler()

        assert agent._scheduler is not None
        assert agent._scheduler.running is True

        # Cleanup
        agent.stop_scheduler()

    @pytest.mark.asyncio
    async def test_stop_calls_shutdown(self):
        agent = DatabaseAgent()
        agent.start_scheduler()
        assert agent._scheduler.running is True

        agent.stop_scheduler()

        # shutdown(wait=False) was called; verify no error raised
        assert agent._scheduler is not None

    def test_stop_without_start(self):
        agent = DatabaseAgent()
        # Should not raise
        agent.stop_scheduler()

    @pytest.mark.asyncio
    async def test_scheduler_has_four_jobs(self):
        agent = DatabaseAgent()
        agent.start_scheduler()

        jobs = agent._scheduler.get_jobs()
        assert len(jobs) == 4

        job_ids = {j.id for j in jobs}
        assert "refresh_stale" in job_ids
        assert "scheduled_discovery" in job_ids
        assert "queue_cleanup" in job_ids
        assert "stall_reaper" in job_ids

        agent.stop_scheduler()
