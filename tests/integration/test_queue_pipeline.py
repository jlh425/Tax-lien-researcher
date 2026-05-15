"""Integration tests for the orchestrator queue-worker pipeline.

Validates the end-to-end flow: queue item -> agent dispatch -> DB state change.

These tests mock the database session and child agents but exercise the real
OrchestratorAgent coordination logic — claim, dispatch, complete/fail, retry,
stall detection, priority ordering, and the run_forever loop.

Run with:
    pytest tests/integration/test_queue_pipeline.py -v
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from aloha.agents.orchestrator.agent import (
    OrchestratorAgent,
    _IDLE_SLEEP_SECONDS,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_queue_item(
    *,
    item_id: int = 1,
    agent_name: str = "scoring",
    payload: dict[str, Any] | None = None,
    parcel_id: str | None = "TEST-001",
    stage: str = "score",
    attempts: int = 0,
) -> dict[str, Any]:
    """Build a dict matching what QueueRepository.claim_one returns."""
    return {
        "id": item_id,
        "agent_name": agent_name,
        "payload": payload or {"parcel_id": parcel_id},
        "parcel_id": parcel_id,
        "stage": stage,
        "attempts": attempts,
    }


def _make_mock_agent(
    *,
    result: dict[str, Any] | None = None,
    side_effect: Exception | None = None,
) -> AsyncMock:
    """Create a mock agent with an async ``run`` method."""
    agent = AsyncMock()
    if side_effect:
        agent.run = AsyncMock(side_effect=side_effect)
    else:
        agent.run = AsyncMock(
            return_value=result if result is not None else {"status": "complete"}
        )
    return agent


class _SessionCtx:
    """Fake async context manager that wraps a mock session."""

    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *args: Any) -> bool:
        return False


def _make_session_and_repo(
    *,
    claim_return: dict[str, Any] | None = None,
    claim_side_effect: list[dict[str, Any] | None] | None = None,
) -> tuple[AsyncMock, MagicMock]:
    """Create a mock session + QueueRepository pair.

    Returns (session_factory, queue_repo_class) ready to be patched.
    """
    session = AsyncMock()
    session.commit = AsyncMock()

    queue_repo = MagicMock()
    queue_repo.claim_one = AsyncMock(
        return_value=claim_return,
        side_effect=claim_side_effect,
    )
    queue_repo.complete = AsyncMock()
    queue_repo.fail = AsyncMock()
    queue_repo.reset_stalled = AsyncMock(return_value=0)

    # session factory returns a context manager yielding the session
    factory = MagicMock()
    factory.return_value = _SessionCtx(session)

    repo_cls = MagicMock(return_value=queue_repo)

    return factory, repo_cls, session, queue_repo


# ═══════════════════════════════════════════════════════════════════════════════
# End-to-end dispatch tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestE2EDispatch:
    """Verify queue item -> correct agent -> item marked complete."""

    @pytest.fixture
    def orchestrator(self) -> OrchestratorAgent:
        return OrchestratorAgent()

    @pytest.mark.parametrize(
        "agent_name",
        [
            "discovery",
            "parcel_research",
            "owner_research",
            "entity_research",
            "enrichment",
            "scoring",
            "report",
            "outreach",
            "zoning",
            "contact_research",
        ],
    )
    async def test_dispatch_to_known_agent_completes(
        self, orchestrator: OrchestratorAgent, agent_name: str
    ) -> None:
        """Each known agent type: claim -> dispatch -> complete."""
        item = _make_queue_item(agent_name=agent_name)
        mock_agent = _make_mock_agent(result={"status": "complete", "data": "ok"})
        orchestrator._dispatch_map = {agent_name: mock_agent}

        factory, repo_cls, session, queue_repo = _make_session_and_repo(
            claim_return=item,
        )

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            processed = await orchestrator._process_one()

        assert processed is True
        mock_agent.run.assert_called_once_with(item["payload"])
        queue_repo.complete.assert_called_once_with(
            item["id"], result={"status": "complete", "data": "ok"}
        )
        session.commit.assert_called()

    async def test_unknown_agent_marks_failed(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """Queue item with unknown agent type -> marked failed immediately."""
        item = _make_queue_item(agent_name="nonexistent_agent")
        orchestrator._dispatch_map = {}  # nothing registered

        factory, repo_cls, session, queue_repo = _make_session_and_repo(
            claim_return=item,
        )

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            processed = await orchestrator._process_one()

        assert processed is True
        queue_repo.fail.assert_called_once()
        fail_call = queue_repo.fail.call_args
        assert fail_call.args[0] == item["id"]
        assert "nonexistent_agent" in fail_call.kwargs["error"]
        # max_attempts=0 means no retry for unknown agents
        assert fail_call.kwargs["max_attempts"] == 0

    async def test_empty_queue_returns_false(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """When no items in queue, _process_one returns False."""
        factory, repo_cls, _, _ = _make_session_and_repo(claim_return=None)

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            processed = await orchestrator._process_one()

        assert processed is False

    async def test_payload_passed_through(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """Agent receives exactly the payload from the queue item."""
        payload = {"parcel_id": "P-999", "county": "natrona", "state": "WY"}
        item = _make_queue_item(agent_name="discovery", payload=payload)
        mock_agent = _make_mock_agent()
        orchestrator._dispatch_map = {"discovery": mock_agent}

        factory, repo_cls, _, _ = _make_session_and_repo(claim_return=item)

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            await orchestrator._process_one()

        mock_agent.run.assert_called_once_with(payload)

    async def test_none_payload_becomes_empty_dict(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """Queue items with no payload pass {} to agent.run."""
        item = _make_queue_item(agent_name="scoring", payload=None)
        # The orchestrator does `payload = item.get("payload") or {}`
        # so None payload becomes {}
        item["payload"] = None
        mock_agent = _make_mock_agent()
        orchestrator._dispatch_map = {"scoring": mock_agent}

        factory, repo_cls, _, _ = _make_session_and_repo(claim_return=item)

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            await orchestrator._process_one()

        mock_agent.run.assert_called_once_with({})


# ═══════════════════════════════════════════════════════════════════════════════
# State machine tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestStateMachine:
    """Verify queue item status transitions through the pipeline."""

    @pytest.fixture
    def orchestrator(self) -> OrchestratorAgent:
        return OrchestratorAgent()

    async def test_success_path_pending_to_complete(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """Item claimed (pending->processing via SQL) -> agent succeeds -> complete."""
        item = _make_queue_item()
        mock_agent = _make_mock_agent(result={"score": 85})
        orchestrator._dispatch_map = {"scoring": mock_agent}

        factory, repo_cls, session, queue_repo = _make_session_and_repo(
            claim_return=item,
        )

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            result = await orchestrator._process_one()

        assert result is True
        # complete is called (not fail)
        queue_repo.complete.assert_called_once_with(
            item["id"], result={"score": 85}
        )
        queue_repo.fail.assert_not_called()

    async def test_failure_path_pending_to_failed(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """Item claimed -> agent raises exception -> fail called."""
        item = _make_queue_item()
        mock_agent = _make_mock_agent(
            side_effect=RuntimeError("LLM timeout")
        )
        orchestrator._dispatch_map = {"scoring": mock_agent}

        factory, repo_cls, session, queue_repo = _make_session_and_repo(
            claim_return=item,
        )

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            result = await orchestrator._process_one()

        assert result is True
        queue_repo.fail.assert_called_once()
        fail_call = queue_repo.fail.call_args
        assert fail_call.args[0] == item["id"]
        assert "LLM timeout" in fail_call.kwargs["error"]
        queue_repo.complete.assert_not_called()

    async def test_failure_commits_session(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """After marking an item failed, the session is committed."""
        item = _make_queue_item()
        mock_agent = _make_mock_agent(
            side_effect=ValueError("bad data")
        )
        orchestrator._dispatch_map = {"scoring": mock_agent}

        factory, repo_cls, session, queue_repo = _make_session_and_repo(
            claim_return=item,
        )

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            await orchestrator._process_one()

        # The orchestrator opens a new session for the fail call and commits it
        session.commit.assert_called()

    async def test_success_commits_session(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """After marking an item complete, the session is committed."""
        item = _make_queue_item()
        mock_agent = _make_mock_agent()
        orchestrator._dispatch_map = {"scoring": mock_agent}

        factory, repo_cls, session, queue_repo = _make_session_and_repo(
            claim_return=item,
        )

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            await orchestrator._process_one()

        session.commit.assert_called()


# ═══════════════════════════════════════════════════════════════════════════════
# Failure recovery tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFailureRecovery:
    """Verify agents that raise exceptions never leave items stuck."""

    @pytest.fixture
    def orchestrator(self) -> OrchestratorAgent:
        return OrchestratorAgent()

    async def test_agent_exception_marks_failed_not_stuck(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """If agent.run raises, the item is marked failed (not left in processing)."""
        item = _make_queue_item()
        mock_agent = _make_mock_agent(
            side_effect=ConnectionError("network down")
        )
        orchestrator._dispatch_map = {"scoring": mock_agent}

        factory, repo_cls, session, queue_repo = _make_session_and_repo(
            claim_return=item,
        )

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            result = await orchestrator._process_one()

        assert result is True
        # fail was called — item is not left in processing state
        queue_repo.fail.assert_called_once()
        assert "network down" in queue_repo.fail.call_args.kwargs["error"]

    async def test_multiple_failures_each_marked_independently(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """Two consecutive failures each get their own fail call."""
        item1 = _make_queue_item(item_id=1)
        item2 = _make_queue_item(item_id=2)
        mock_agent = _make_mock_agent(
            side_effect=RuntimeError("crash")
        )
        orchestrator._dispatch_map = {"scoring": mock_agent}

        factory, repo_cls, session, queue_repo = _make_session_and_repo(
            claim_side_effect=[item1, item2],
        )

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            await orchestrator._process_one()
            await orchestrator._process_one()

        assert queue_repo.fail.call_count == 2
        fail_ids = [c.args[0] for c in queue_repo.fail.call_args_list]
        assert fail_ids == [1, 2]

    async def test_unknown_agent_does_not_retry(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """Unknown agent type sets max_attempts=0 so the repo marks it permanently failed."""
        item = _make_queue_item(agent_name="bogus")
        orchestrator._dispatch_map = {}

        factory, repo_cls, session, queue_repo = _make_session_and_repo(
            claim_return=item,
        )

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            await orchestrator._process_one()

        queue_repo.fail.assert_called_once()
        assert queue_repo.fail.call_args.kwargs["max_attempts"] == 0

    async def test_agent_error_preserves_error_message(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """The full error message is passed to repo.fail."""
        item = _make_queue_item()
        err_msg = "Detailed error: API rate limit at 2025-01-15T10:00:00Z"
        mock_agent = _make_mock_agent(side_effect=RuntimeError(err_msg))
        orchestrator._dispatch_map = {"scoring": mock_agent}

        factory, repo_cls, session, queue_repo = _make_session_and_repo(
            claim_return=item,
        )

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            await orchestrator._process_one()

        assert queue_repo.fail.call_args.kwargs["error"] == err_msg


# ═══════════════════════════════════════════════════════════════════════════════
# Stall reaper tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestStallReaper:
    """Verify the stall reaper resets stuck processing items."""

    @pytest.fixture
    def orchestrator(self) -> OrchestratorAgent:
        return OrchestratorAgent()

    async def test_stall_reaper_calls_reset_stalled(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """The stall reaper calls reset_stalled on the repo."""
        session = AsyncMock()
        session.commit = AsyncMock()
        queue_repo = MagicMock()
        queue_repo.reset_stalled = AsyncMock(return_value=3)

        factory = MagicMock()
        factory.return_value = _SessionCtx(session)
        repo_cls = MagicMock(return_value=queue_repo)

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
            patch(
                "aloha.agents.orchestrator.agent._STALL_REAPER_INTERVAL", 0.01
            ),
        ):
            # Run the reaper loop briefly then cancel
            task = asyncio.create_task(orchestrator._stall_reaper_loop())
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        queue_repo.reset_stalled.assert_called()
        assert queue_repo.reset_stalled.call_args.kwargs["stalled_after_minutes"] == 30
        session.commit.assert_called()

    async def test_stall_reaper_handles_exceptions_gracefully(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """The stall reaper logs but does not crash on exceptions."""
        session = AsyncMock()
        queue_repo = MagicMock()
        queue_repo.reset_stalled = AsyncMock(
            side_effect=RuntimeError("DB connection lost")
        )

        factory = MagicMock()
        factory.return_value = _SessionCtx(session)
        repo_cls = MagicMock(return_value=queue_repo)

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
            patch(
                "aloha.agents.orchestrator.agent._STALL_REAPER_INTERVAL", 0.01
            ),
        ):
            task = asyncio.create_task(orchestrator._stall_reaper_loop())
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Should have attempted multiple times without crashing
        assert queue_repo.reset_stalled.call_count >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# run_forever loop tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunForever:
    """Verify the main event loop: process items, sleep when idle, stop cleanly."""

    @pytest.fixture
    def orchestrator(self) -> OrchestratorAgent:
        return OrchestratorAgent()

    async def test_processes_items_until_stopped(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """run_forever processes items and stops when stop() is called."""
        call_count = 0

        async def mock_process_one() -> bool:
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                orchestrator.stop()
            return True

        orchestrator._process_one = mock_process_one  # type: ignore[assignment]
        orchestrator._build_dispatch_map = MagicMock()

        with patch(
            "aloha.agents.orchestrator.agent._STALL_REAPER_INTERVAL", 9999
        ):
            await asyncio.wait_for(orchestrator.run_forever(), timeout=5.0)

        assert call_count == 3

    async def test_sleeps_when_queue_empty(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """When _process_one returns False (empty queue), the loop sleeps."""
        call_count = 0

        async def mock_process_one() -> bool:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                orchestrator.stop()
            return False  # empty queue

        orchestrator._process_one = mock_process_one  # type: ignore[assignment]
        orchestrator._build_dispatch_map = MagicMock()

        sleep_calls: list[float] = []
        original_sleep = asyncio.sleep

        async def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)
            # Don't actually sleep — just record
            await original_sleep(0)

        with (
            patch("asyncio.sleep", mock_sleep),
            patch(
                "aloha.agents.orchestrator.agent._STALL_REAPER_INTERVAL", 9999
            ),
        ):
            await asyncio.wait_for(orchestrator.run_forever(), timeout=5.0)

        # Should have slept with _IDLE_SLEEP_SECONDS
        assert any(s == _IDLE_SLEEP_SECONDS for s in sleep_calls)

    async def test_exception_in_process_one_does_not_crash_loop(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """If _process_one raises, the loop catches it and continues."""
        call_count = 0

        async def mock_process_one() -> bool:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient DB error")
            if call_count >= 3:
                orchestrator.stop()
            return True

        orchestrator._process_one = mock_process_one  # type: ignore[assignment]
        orchestrator._build_dispatch_map = MagicMock()

        sleep_calls: list[float] = []
        original_sleep = asyncio.sleep

        async def mock_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)
            await original_sleep(0)

        with (
            patch("asyncio.sleep", mock_sleep),
            patch(
                "aloha.agents.orchestrator.agent._STALL_REAPER_INTERVAL", 9999
            ),
        ):
            await asyncio.wait_for(orchestrator.run_forever(), timeout=5.0)

        # Loop survived the exception and processed more items
        assert call_count == 3

    async def test_stall_reaper_cancelled_on_shutdown(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """When the loop exits, the stall reaper task is cancelled."""
        orchestrator._build_dispatch_map = MagicMock()

        reaper_task_mock = AsyncMock()
        reaper_task_mock.cancel = MagicMock()

        call_count = 0

        async def mock_process_one() -> bool:
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                orchestrator.stop()
            return True

        orchestrator._process_one = mock_process_one  # type: ignore[assignment]

        with patch(
            "asyncio.create_task", return_value=reaper_task_mock
        ):
            await asyncio.wait_for(orchestrator.run_forever(), timeout=5.0)

        reaper_task_mock.cancel.assert_called_once()

    async def test_running_flag_set_during_execution(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """_running is True while run_forever is active."""
        observed_running = []

        async def mock_process_one() -> bool:
            observed_running.append(orchestrator._running)
            orchestrator.stop()
            return True

        orchestrator._process_one = mock_process_one  # type: ignore[assignment]
        orchestrator._build_dispatch_map = MagicMock()

        with patch(
            "aloha.agents.orchestrator.agent._STALL_REAPER_INTERVAL", 9999
        ):
            await asyncio.wait_for(orchestrator.run_forever(), timeout=5.0)

        assert observed_running == [True]
        assert orchestrator._running is False


# ═══════════════════════════════════════════════════════════════════════════════
# OrchestratorAgent.run (one-shot mode) integration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOneShotRun:
    """Verify the .run() method used in tests / one-shot mode."""

    @pytest.fixture
    def orchestrator(self) -> OrchestratorAgent:
        return OrchestratorAgent()

    async def test_run_delegates_to_agent(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """run() calls the named agent and returns its result."""
        mock_agent = _make_mock_agent(result={"score": 92, "status": "complete"})
        orchestrator._dispatch_map = {"scoring": mock_agent}

        result = await orchestrator.run({
            "item_id": 10,
            "agent_name": "scoring",
            "payload": {"parcel_id": "ABC"},
        })

        assert result == {"score": 92, "status": "complete"}
        mock_agent.run.assert_called_once_with({"parcel_id": "ABC"})

    async def test_run_unknown_agent_returns_error(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """run() with unknown agent returns error dict (no exception)."""
        orchestrator._dispatch_map = {}

        result = await orchestrator.run({
            "item_id": 10,
            "agent_name": "fake_agent",
            "payload": {},
        })

        assert result["status"] == "error"
        assert "fake_agent" in result["reason"]

    async def test_run_propagates_agent_exception(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """In one-shot mode, agent exceptions propagate to caller."""
        mock_agent = _make_mock_agent(side_effect=RuntimeError("boom"))
        orchestrator._dispatch_map = {"scoring": mock_agent}

        with pytest.raises(RuntimeError, match="boom"):
            await orchestrator.run({
                "item_id": 10,
                "agent_name": "scoring",
                "payload": {},
            })


# ═══════════════════════════════════════════════════════════════════════════════
# Dispatch map tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDispatchMap:
    """Verify agent dispatch map construction and lookup."""

    @pytest.fixture
    def orchestrator(self) -> OrchestratorAgent:
        return OrchestratorAgent()

    def test_build_dispatch_map_registers_all_agents(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """_build_dispatch_map populates all expected agent keys."""
        orchestrator._build_dispatch_map()

        expected_agents = {
            "discovery",
            "parcel_research",
            "owner_research",
            "entity_research",
            "contact_research",
            "enrichment",
            "scoring",
            "report",
            "outreach",
            "zoning",
        }
        assert set(orchestrator._dispatch_map.keys()) == expected_agents

    def test_get_agent_lazy_builds(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """_get_agent builds the dispatch map on first access."""
        assert orchestrator._dispatch_map == {}
        agent = orchestrator._get_agent("scoring")
        assert orchestrator._dispatch_map != {}
        assert agent is not None

    def test_get_agent_returns_none_for_unknown(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """_get_agent returns None for unregistered agent names."""
        orchestrator._dispatch_map = {"scoring": MagicMock()}
        assert orchestrator._get_agent("nonexistent") is None


# ═══════════════════════════════════════════════════════════════════════════════
# Multi-item processing sequence tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestProcessingSequence:
    """Verify correct behaviour when processing multiple items in sequence."""

    @pytest.fixture
    def orchestrator(self) -> OrchestratorAgent:
        return OrchestratorAgent()

    async def test_success_then_failure_handled_independently(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """First item succeeds, second fails — each gets correct status."""
        item1 = _make_queue_item(item_id=1, agent_name="scoring")
        item2 = _make_queue_item(item_id=2, agent_name="report")

        scoring_agent = _make_mock_agent(result={"score": 75})
        report_agent = _make_mock_agent(
            side_effect=TimeoutError("LLM timeout")
        )
        orchestrator._dispatch_map = {
            "scoring": scoring_agent,
            "report": report_agent,
        }

        factory, repo_cls, session, queue_repo = _make_session_and_repo(
            claim_side_effect=[item1, item2],
        )

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            result1 = await orchestrator._process_one()
            result2 = await orchestrator._process_one()

        assert result1 is True
        assert result2 is True

        # First item completed
        queue_repo.complete.assert_called_once_with(1, result={"score": 75})
        # Second item failed
        queue_repo.fail.assert_called_once()
        assert queue_repo.fail.call_args.args[0] == 2

    async def test_mixed_agent_types_dispatched_correctly(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """Different agent types in sequence are each dispatched correctly."""
        items = [
            _make_queue_item(item_id=1, agent_name="discovery"),
            _make_queue_item(item_id=2, agent_name="scoring"),
            _make_queue_item(item_id=3, agent_name="report"),
        ]

        agents = {
            "discovery": _make_mock_agent(result={"records_found": 10}),
            "scoring": _make_mock_agent(result={"score": 80}),
            "report": _make_mock_agent(result={"report_id": "R-1"}),
        }
        orchestrator._dispatch_map = agents

        factory, repo_cls, session, queue_repo = _make_session_and_repo(
            claim_side_effect=items,
        )

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            for _ in range(3):
                await orchestrator._process_one()

        assert queue_repo.complete.call_count == 3
        completed_ids = [c.args[0] for c in queue_repo.complete.call_args_list]
        assert completed_ids == [1, 2, 3]

        agents["discovery"].run.assert_called_once()
        agents["scoring"].run.assert_called_once()
        agents["report"].run.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Agent result handling
# ═══════════════════════════════════════════════════════════════════════════════


class TestResultHandling:
    """Verify agent results are correctly passed to queue_repo.complete."""

    @pytest.fixture
    def orchestrator(self) -> OrchestratorAgent:
        return OrchestratorAgent()

    async def test_agent_result_stored_on_complete(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """The result dict from agent.run is passed to repo.complete."""
        expected_result = {
            "status": "complete",
            "score": 92,
            "flags": ["high_value", "clear_title"],
        }
        item = _make_queue_item()
        mock_agent = _make_mock_agent(result=expected_result)
        orchestrator._dispatch_map = {"scoring": mock_agent}

        factory, repo_cls, session, queue_repo = _make_session_and_repo(
            claim_return=item,
        )

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            await orchestrator._process_one()

        queue_repo.complete.assert_called_once_with(
            item["id"], result=expected_result
        )

    async def test_empty_result_dict_stored(
        self, orchestrator: OrchestratorAgent
    ) -> None:
        """An empty result dict is still stored correctly."""
        item = _make_queue_item()
        mock_agent = _make_mock_agent(result={})
        orchestrator._dispatch_map = {"scoring": mock_agent}

        factory, repo_cls, session, queue_repo = _make_session_and_repo(
            claim_return=item,
        )

        with (
            patch(
                "aloha.agents.orchestrator.agent.async_session_factory", factory
            ),
            patch(
                "aloha.agents.orchestrator.agent.QueueRepository", repo_cls
            ),
        ):
            await orchestrator._process_one()

        queue_repo.complete.assert_called_once_with(item["id"], result={})
