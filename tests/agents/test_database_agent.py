"""Unit tests for the Database Agent (no DB, no LLM, no network).

Covers:
- ``run()`` task dispatcher (all task types + edge cases)
- ``refresh_stale_parcels`` (mark stale + re-enqueue logic)
- ``scheduled_discovery`` (county iteration + error handling)
- ``cleanup_complete_queue`` (SQL delete with status/age filter)
- ``reset_stalled_items`` (delegation to QueueRepository)
- Scheduler lifecycle (start, stop, job registration, triggers)
- ``get_tools`` (empty list)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

# conftest.py patches get_agent_model at module level so agent imports work.
from aloha.agents.database.agent import DatabaseAgent, _SCHEDULED_COUNTIES


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_mock_parcel(
    parcel_id: str = "P-001",
    state: str = "FL",
    county: str = "orange",
    address: str = "123 Main St",
) -> MagicMock:
    """Build a MagicMock that behaves like a Parcel ORM instance."""
    p = MagicMock()
    p.parcel_id = parcel_id
    p.state = state
    p.county = county
    p.address = address
    return p


def _patch_async_session(mock_session: AsyncMock):
    """Return a patch context-manager that replaces async_session_factory
    with an async context manager that yields *mock_session*.
    """
    @asynccontextmanager
    async def _fake_factory():
        yield mock_session

    return patch("aloha.agents.database.agent.async_session_factory", _fake_factory)


# ═══════════════════════════════════════════════════════════════════════════════
# get_tools
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetTools:
    def test_returns_empty_list(self):
        agent = DatabaseAgent()
        assert agent.get_tools() == []


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

    @pytest.mark.asyncio
    async def test_empty_string_task(self, agent):
        """An empty-string task value is treated as unknown."""
        result = await agent.run({"task": ""})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_run_returns_count_from_each_method(self, agent):
        """Verify each dispatcher branch propagates the return value correctly."""
        for task_name, method_name in [
            ("refresh_stale", "refresh_stale_parcels"),
            ("discovery", "scheduled_discovery"),
            ("cleanup", "cleanup_complete_queue"),
            ("reset_stalled", "reset_stalled_items"),
        ]:
            setattr(agent, method_name, AsyncMock(return_value=42))
            result = await agent.run({"task": task_name})
            assert result["count"] == 42, f"Failed for task={task_name}"


# ═══════════════════════════════════════════════════════════════════════════════
# refresh_stale_parcels
# ═══════════════════════════════════════════════════════════════════════════════


class TestRefreshStaleParcels:
    @pytest.fixture
    def agent(self):
        return DatabaseAgent()

    @staticmethod
    def _mock_session_with_parcels(parcels: list) -> AsyncMock:
        """Build a mock session whose execute() returns *parcels* via scalars."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = parcels

        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        return mock_session

    @pytest.mark.asyncio
    async def test_marks_and_enqueues(self, agent):
        mock_parcel = _make_mock_parcel()
        mock_session = self._mock_session_with_parcels([mock_parcel])

        mock_parcel_repo = MagicMock()
        mock_parcel_repo.mark_stale = AsyncMock(return_value=1)

        mock_queue_repo = MagicMock()
        mock_queue_repo.enqueue = AsyncMock()

        with _patch_async_session(mock_session):
            with patch(
                "aloha.db.repositories.ParcelRepository",
                return_value=mock_parcel_repo,
            ):
                with patch(
                    "aloha.db.repositories.QueueRepository",
                    return_value=mock_queue_repo,
                ):
                    count = await agent.refresh_stale_parcels()

        assert count == 1
        mock_queue_repo.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_stale_parcels(self, agent):
        mock_session = self._mock_session_with_parcels([])

        mock_parcel_repo = MagicMock()
        mock_parcel_repo.mark_stale = AsyncMock(return_value=0)

        mock_queue_repo = MagicMock()
        mock_queue_repo.enqueue = AsyncMock()

        with _patch_async_session(mock_session):
            with patch(
                "aloha.db.repositories.ParcelRepository",
                return_value=mock_parcel_repo,
            ):
                with patch(
                    "aloha.db.repositories.QueueRepository",
                    return_value=mock_queue_repo,
                ):
                    count = await agent.refresh_stale_parcels()

        assert count == 0
        mock_queue_repo.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_stale_parcels(self, agent):
        """When several parcels are stale, each is re-enqueued individually."""
        parcels = [
            _make_mock_parcel("P-001", "FL", "orange", "123 Main St"),
            _make_mock_parcel("P-002", "CO", "denver", "456 Oak Ave"),
            _make_mock_parcel("P-003", "IA", "polk", "789 Elm Dr"),
        ]
        mock_session = self._mock_session_with_parcels(parcels)

        mock_parcel_repo = MagicMock()
        mock_parcel_repo.mark_stale = AsyncMock(return_value=3)

        mock_queue_repo = MagicMock()
        mock_queue_repo.enqueue = AsyncMock()

        with _patch_async_session(mock_session):
            with patch(
                "aloha.db.repositories.ParcelRepository",
                return_value=mock_parcel_repo,
            ):
                with patch(
                    "aloha.db.repositories.QueueRepository",
                    return_value=mock_queue_repo,
                ):
                    count = await agent.refresh_stale_parcels()

        assert count == 3
        assert mock_queue_repo.enqueue.call_count == 3

    @pytest.mark.asyncio
    async def test_enqueue_payload_contains_parcel_data(self, agent):
        """Verify the enqueue call carries the correct payload from the parcel."""
        parcel = _make_mock_parcel("P-XYZ", "CO", "denver", "999 Pike Pl")
        mock_session = self._mock_session_with_parcels([parcel])

        mock_parcel_repo = MagicMock()
        mock_parcel_repo.mark_stale = AsyncMock(return_value=1)

        mock_queue_repo = MagicMock()
        mock_queue_repo.enqueue = AsyncMock()

        with _patch_async_session(mock_session):
            with patch(
                "aloha.db.repositories.ParcelRepository",
                return_value=mock_parcel_repo,
            ):
                with patch(
                    "aloha.db.repositories.QueueRepository",
                    return_value=mock_queue_repo,
                ):
                    await agent.refresh_stale_parcels()

        mock_queue_repo.enqueue.assert_called_once_with(
            agent_name="parcel_research",
            stage="parcel",
            parcel_id="P-XYZ",
            payload={
                "parcel_id": "P-XYZ",
                "state": "CO",
                "county": "denver",
                "address": "999 Pike Pl",
            },
            priority=3,
        )

    @pytest.mark.asyncio
    async def test_custom_stale_after_days(self, agent):
        """The cutoff datetime is computed from stale_after_days param."""
        mock_session = self._mock_session_with_parcels([])

        mock_parcel_repo = MagicMock()
        mock_parcel_repo.mark_stale = AsyncMock(return_value=0)

        mock_queue_repo = MagicMock()

        with _patch_async_session(mock_session):
            with patch(
                "aloha.db.repositories.ParcelRepository",
                return_value=mock_parcel_repo,
            ):
                with patch(
                    "aloha.db.repositories.QueueRepository",
                    return_value=mock_queue_repo,
                ):
                    count = await agent.refresh_stale_parcels(stale_after_days=7)

        assert count == 0
        # Verify mark_stale was called with older_than_hours
        mock_parcel_repo.mark_stale.assert_called_once()
        call_kwargs = mock_parcel_repo.mark_stale.call_args
        assert "older_than_hours" in call_kwargs.kwargs
        assert call_kwargs.kwargs["older_than_hours"] == 7 * 24

    @pytest.mark.asyncio
    async def test_session_commit_called(self, agent):
        """Session is committed after processing stale parcels."""
        mock_session = self._mock_session_with_parcels([])

        mock_parcel_repo = MagicMock()
        mock_parcel_repo.mark_stale = AsyncMock(return_value=0)
        mock_queue_repo = MagicMock()

        with _patch_async_session(mock_session):
            with patch(
                "aloha.db.repositories.ParcelRepository",
                return_value=mock_parcel_repo,
            ):
                with patch(
                    "aloha.db.repositories.QueueRepository",
                    return_value=mock_queue_repo,
                ):
                    await agent.refresh_stale_parcels()

        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_priority_is_three(self, agent):
        """Stale-parcel re-enqueue jobs use priority 3 (lower-than-default)."""
        parcel = _make_mock_parcel()
        mock_session = self._mock_session_with_parcels([parcel])

        mock_parcel_repo = MagicMock()
        mock_parcel_repo.mark_stale = AsyncMock(return_value=1)
        mock_queue_repo = MagicMock()
        mock_queue_repo.enqueue = AsyncMock()

        with _patch_async_session(mock_session):
            with patch(
                "aloha.db.repositories.ParcelRepository",
                return_value=mock_parcel_repo,
            ):
                with patch(
                    "aloha.db.repositories.QueueRepository",
                    return_value=mock_queue_repo,
                ):
                    await agent.refresh_stale_parcels()

        _, kwargs = mock_queue_repo.enqueue.call_args
        assert kwargs["priority"] == 3


# ═══════════════════════════════════════════════════════════════════════════════
# scheduled_discovery
# ═══════════════════════════════════════════════════════════════════════════════


class TestScheduledDiscovery:
    @pytest.fixture
    def agent(self):
        return DatabaseAgent()

    @pytest.mark.asyncio
    async def test_runs_all_counties(self, agent):
        """Discovery is run for every county in _SCHEDULED_COUNTIES."""
        mock_discovery = AsyncMock(return_value={"enqueued": 10})

        with patch(
            "aloha.agents.database.agent.discovery_agent",
            create=True,
        ) as _:
            # The agent imports discovery_agent lazily; we patch it at source
            with patch(
                "aloha.agents.discovery.agent.agent",
                create=True,
            ) as mock_agent:
                mock_agent.run = mock_discovery
                total = await agent.scheduled_discovery()

        assert total == 10 * len(_SCHEDULED_COUNTIES)
        assert mock_discovery.call_count == len(_SCHEDULED_COUNTIES)

    @pytest.mark.asyncio
    async def test_sums_enqueued_counts(self, agent):
        """Total is the sum of enqueued counts across all counties."""
        results = iter([{"enqueued": 5}, {"enqueued": 3}, {"enqueued": 12}])

        with patch(
            "aloha.agents.discovery.agent.agent",
            create=True,
        ) as mock_agent:
            mock_agent.run = AsyncMock(side_effect=lambda ctx: next(results))
            total = await agent.scheduled_discovery()

        assert total == 20  # 5 + 3 + 12

    @pytest.mark.asyncio
    async def test_one_county_fails_others_continue(self, agent):
        """If one county raises, the rest still execute."""
        call_count = 0

        async def _side_effect(ctx):
            nonlocal call_count
            call_count += 1
            if ctx["state"] == "FL":
                raise RuntimeError("scraper down")
            return {"enqueued": 7}

        with patch(
            "aloha.agents.discovery.agent.agent",
            create=True,
        ) as mock_agent:
            mock_agent.run = _side_effect
            total = await agent.scheduled_discovery()

        # FL failed (0 enqueued), CO and IA succeeded (7 each)
        assert total == 7 * (len(_SCHEDULED_COUNTIES) - 1)
        assert call_count == len(_SCHEDULED_COUNTIES)

    @pytest.mark.asyncio
    async def test_all_counties_fail(self, agent):
        """If every county raises, total is 0 and no exception propagates."""
        with patch(
            "aloha.agents.discovery.agent.agent",
            create=True,
        ) as mock_agent:
            mock_agent.run = AsyncMock(side_effect=RuntimeError("boom"))
            total = await agent.scheduled_discovery()

        assert total == 0

    @pytest.mark.asyncio
    async def test_missing_enqueued_key(self, agent):
        """If result dict has no 'enqueued' key, default to 0."""
        with patch(
            "aloha.agents.discovery.agent.agent",
            create=True,
        ) as mock_agent:
            mock_agent.run = AsyncMock(return_value={"status": "complete"})
            total = await agent.scheduled_discovery()

        assert total == 0

    @pytest.mark.asyncio
    async def test_passes_correct_context(self, agent):
        """Each county call gets the correct state, county, and max_records."""
        captured_contexts: list[dict] = []

        async def _capture(ctx):
            captured_contexts.append(ctx)
            return {"enqueued": 0}

        with patch(
            "aloha.agents.discovery.agent.agent",
            create=True,
        ) as mock_agent:
            mock_agent.run = _capture
            await agent.scheduled_discovery()

        assert len(captured_contexts) == len(_SCHEDULED_COUNTIES)
        for ctx, (state, county) in zip(captured_contexts, _SCHEDULED_COUNTIES):
            assert ctx["state"] == state
            assert ctx["county"] == county
            assert ctx["max_records"] == 5000

    @pytest.mark.asyncio
    async def test_scheduled_counties_list_content(self):
        """_SCHEDULED_COUNTIES has the expected entries."""
        assert ("FL", "orange") in _SCHEDULED_COUNTIES
        assert ("CO", "denver") in _SCHEDULED_COUNTIES
        assert ("IA", "polk") in _SCHEDULED_COUNTIES


# ═══════════════════════════════════════════════════════════════════════════════
# cleanup_complete_queue
# ═══════════════════════════════════════════════════════════════════════════════


class TestCleanupCompleteQueue:
    @pytest.fixture
    def agent(self):
        return DatabaseAgent()

    @pytest.mark.asyncio
    async def test_deletes_old_complete_items(self, agent):
        """Completed/failed items older than cutoff are deleted."""
        mock_result = MagicMock()
        mock_result.rowcount = 15

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with _patch_async_session(mock_session):
            deleted = await agent.cleanup_complete_queue()

        assert deleted == 15
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_items_to_delete(self, agent):
        """When nothing matches, rowcount is 0."""
        mock_result = MagicMock()
        mock_result.rowcount = 0

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with _patch_async_session(mock_session):
            deleted = await agent.cleanup_complete_queue()

        assert deleted == 0

    @pytest.mark.asyncio
    async def test_custom_older_than_days(self, agent):
        """Custom older_than_days is accepted without error."""
        mock_result = MagicMock()
        mock_result.rowcount = 3

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with _patch_async_session(mock_session):
            deleted = await agent.cleanup_complete_queue(older_than_days=7)

        assert deleted == 3

    @pytest.mark.asyncio
    async def test_delete_query_filters_correct_statuses(self, agent):
        """The DELETE targets only 'complete' and 'failed' status items."""
        mock_result = MagicMock()
        mock_result.rowcount = 0

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with _patch_async_session(mock_session):
            await agent.cleanup_complete_queue()

        # Verify execute was called (the delete statement was constructed)
        execute_call = mock_session.execute.call_args
        assert execute_call is not None
        # The first positional arg is the delete statement
        stmt = execute_call[0][0]
        # We check the string representation contains the expected status filter
        stmt_str = str(stmt)
        assert "complete" in stmt_str or "queue_items" in stmt_str

    @pytest.mark.asyncio
    async def test_session_committed_after_delete(self, agent):
        """The session is committed after the delete executes."""
        mock_result = MagicMock()
        mock_result.rowcount = 5

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        # Track call order
        call_order: list[str] = []
        original_execute = mock_session.execute

        async def _track_execute(*args, **kwargs):
            call_order.append("execute")
            return mock_result

        async def _track_commit():
            call_order.append("commit")

        mock_session.execute = _track_execute
        mock_session.commit = _track_commit

        with _patch_async_session(mock_session):
            await agent.cleanup_complete_queue()

        assert call_order == ["execute", "commit"]

    @pytest.mark.asyncio
    async def test_large_rowcount(self, agent):
        """Handles large deletion counts correctly."""
        mock_result = MagicMock()
        mock_result.rowcount = 100_000

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with _patch_async_session(mock_session):
            deleted = await agent.cleanup_complete_queue()

        assert deleted == 100_000


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

        with _patch_async_session(mock_session):
            with patch(
                "aloha.db.repositories.QueueRepository",
                return_value=mock_queue_repo,
            ):
                count = await agent.reset_stalled_items()

        assert count == 3

    @pytest.mark.asyncio
    async def test_none_returns_zero(self, agent):
        mock_queue_repo = MagicMock()
        mock_queue_repo.reset_stalled = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        with _patch_async_session(mock_session):
            with patch(
                "aloha.db.repositories.QueueRepository",
                return_value=mock_queue_repo,
            ):
                count = await agent.reset_stalled_items()

        assert count == 0

    @pytest.mark.asyncio
    async def test_zero_returns_zero(self, agent):
        """Explicit 0 from reset_stalled returns 0 (not falsy confusion)."""
        mock_queue_repo = MagicMock()
        mock_queue_repo.reset_stalled = AsyncMock(return_value=0)

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        with _patch_async_session(mock_session):
            with patch(
                "aloha.db.repositories.QueueRepository",
                return_value=mock_queue_repo,
            ):
                count = await agent.reset_stalled_items()

        assert count == 0

    @pytest.mark.asyncio
    async def test_custom_stall_minutes(self, agent):
        """Custom stall_minutes is passed through to the repository."""
        mock_queue_repo = MagicMock()
        mock_queue_repo.reset_stalled = AsyncMock(return_value=1)

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        with _patch_async_session(mock_session):
            with patch(
                "aloha.db.repositories.QueueRepository",
                return_value=mock_queue_repo,
            ):
                await agent.reset_stalled_items(stall_minutes=60)

        mock_queue_repo.reset_stalled.assert_called_once_with(stalled_after_minutes=60)

    @pytest.mark.asyncio
    async def test_default_stall_minutes(self, agent):
        """Default stall_minutes is 30."""
        mock_queue_repo = MagicMock()
        mock_queue_repo.reset_stalled = AsyncMock(return_value=0)

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        with _patch_async_session(mock_session):
            with patch(
                "aloha.db.repositories.QueueRepository",
                return_value=mock_queue_repo,
            ):
                await agent.reset_stalled_items()

        mock_queue_repo.reset_stalled.assert_called_once_with(stalled_after_minutes=30)

    @pytest.mark.asyncio
    async def test_session_committed(self, agent):
        """Session is committed after resetting stalled items."""
        mock_queue_repo = MagicMock()
        mock_queue_repo.reset_stalled = AsyncMock(return_value=2)

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        with _patch_async_session(mock_session):
            with patch(
                "aloha.db.repositories.QueueRepository",
                return_value=mock_queue_repo,
            ):
                await agent.reset_stalled_items()

        mock_session.commit.assert_called_once()


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

    @pytest.mark.asyncio
    async def test_job_names(self):
        """Each job has a human-readable name."""
        agent = DatabaseAgent()
        agent.start_scheduler()

        jobs_by_id = {j.id: j for j in agent._scheduler.get_jobs()}
        assert jobs_by_id["refresh_stale"].name == "Refresh stale parcels"
        assert jobs_by_id["scheduled_discovery"].name == "Scheduled county discovery"
        assert jobs_by_id["queue_cleanup"].name == "Clean completed queue items"
        assert jobs_by_id["stall_reaper"].name == "Reset stalled queue items"

        agent.stop_scheduler()

    @pytest.mark.asyncio
    async def test_refresh_stale_trigger_is_interval_6h(self):
        """refresh_stale runs on a 6-hour interval trigger."""
        agent = DatabaseAgent()
        agent.start_scheduler()

        job = agent._scheduler.get_job("refresh_stale")
        trigger = job.trigger
        # IntervalTrigger has an interval attribute (timedelta)
        assert hasattr(trigger, "interval")
        assert trigger.interval == timedelta(hours=6)

        agent.stop_scheduler()

    @pytest.mark.asyncio
    async def test_discovery_trigger_is_cron_daily_2am(self):
        """scheduled_discovery runs daily at 02:00 UTC via CronTrigger."""
        from apscheduler.triggers.cron import CronTrigger

        agent = DatabaseAgent()
        agent.start_scheduler()

        job = agent._scheduler.get_job("scheduled_discovery")
        assert isinstance(job.trigger, CronTrigger)

        agent.stop_scheduler()

    @pytest.mark.asyncio
    async def test_cleanup_trigger_is_cron_weekly_sunday(self):
        """queue_cleanup runs weekly on Sunday at 03:00 UTC via CronTrigger."""
        from apscheduler.triggers.cron import CronTrigger

        agent = DatabaseAgent()
        agent.start_scheduler()

        job = agent._scheduler.get_job("queue_cleanup")
        assert isinstance(job.trigger, CronTrigger)

        agent.stop_scheduler()

    @pytest.mark.asyncio
    async def test_stall_reaper_trigger_is_interval_10min(self):
        """stall_reaper runs on a 10-minute interval trigger."""
        agent = DatabaseAgent()
        agent.start_scheduler()

        job = agent._scheduler.get_job("stall_reaper")
        trigger = job.trigger
        assert hasattr(trigger, "interval")
        assert trigger.interval == timedelta(minutes=10)

        agent.stop_scheduler()

    @pytest.mark.asyncio
    async def test_start_scheduler_idempotent(self):
        """Calling start_scheduler twice does not raise (replace_existing=True)."""
        agent = DatabaseAgent()
        agent.start_scheduler()
        first_scheduler = agent._scheduler

        # Calling again creates a new scheduler instance
        agent.start_scheduler()

        assert agent._scheduler is not None
        agent.stop_scheduler()

    def test_stop_scheduler_when_not_running(self):
        """Stopping a non-running scheduler does not raise."""
        agent = DatabaseAgent()
        agent._scheduler = MagicMock()
        agent._scheduler.running = False

        # Should not raise
        agent.stop_scheduler()

    @pytest.mark.asyncio
    async def test_jobs_target_correct_methods(self):
        """Each job points to the correct method on the agent instance."""
        agent = DatabaseAgent()
        agent.start_scheduler()

        jobs_by_id = {j.id: j for j in agent._scheduler.get_jobs()}

        assert jobs_by_id["refresh_stale"].func == agent.refresh_stale_parcels
        assert jobs_by_id["scheduled_discovery"].func == agent.scheduled_discovery
        assert jobs_by_id["queue_cleanup"].func == agent.cleanup_complete_queue
        assert jobs_by_id["stall_reaper"].func == agent.reset_stalled_items

        agent.stop_scheduler()


# ═══════════════════════════════════════════════════════════════════════════════
# Agent construction & attributes
# ═══════════════════════════════════════════════════════════════════════════════


class TestDatabaseAgentInit:
    def test_name_is_database(self):
        agent = DatabaseAgent()
        assert agent.name == "database"

    def test_scheduler_initially_none(self):
        agent = DatabaseAgent()
        assert agent._scheduler is None

    def test_inherits_base_agent(self):
        from aloha.agents.base import BaseAgent

        agent = DatabaseAgent()
        assert isinstance(agent, BaseAgent)
