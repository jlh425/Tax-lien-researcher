"""Orchestrator Agent — top-level queue consumer that dispatches to all agents.

The Orchestrator runs as a long-lived background worker.  It continuously
claims queue items (using SKIP LOCKED) and dispatches them to the appropriate
specialised agent.

Agent dispatch map:
  parcel_research  → ParcelResearchAgent
  owner_research   → OwnerResearchAgent
  entity_research  → EntityResearchAgent
  scoring          → ScoringAgent
  report           → ReportAgent
  discovery        → DiscoveryAgent  (for on-demand / scheduled scans)

Design:
- Claims one item at a time per worker (controlled concurrency via multiple workers)
- Marks items complete on success, failed with exponential backoff on exception
- Stalled-item reaper runs periodically to rescue stuck jobs
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from aloha.agents.base import BaseAgent
from aloha.db.engine import async_session_factory
from aloha.db.repositories import QueueRepository

log = structlog.get_logger().bind(agent="orchestrator")

# How long to wait between poll cycles when the queue is empty (seconds)
_IDLE_SLEEP_SECONDS = 5.0
# How often to run the stalled-item reaper (seconds)
_STALL_REAPER_INTERVAL = 300.0


class OrchestratorAgent(BaseAgent):
    """Queue worker that dispatches to specialised research agents.

    Runs via ``run_forever()`` in an asyncio task.  Shutdown is signalled
    by setting ``self._running = False``.
    """

    def __init__(self) -> None:
        super().__init__(name="orchestrator")
        self._running = False
        self._dispatch_map: dict[str, BaseAgent] = {}

    def get_tools(self) -> list[dict[str, Any]]:
        return []

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Process a single queue item (used in tests / one-shot mode)."""
        context["item_id"]
        agent_name: str = context["agent_name"]
        payload: dict[str, Any] = context["payload"]

        agent = self._get_agent(agent_name)
        if agent is None:
            return {"status": "error", "reason": f"Unknown agent: {agent_name!r}"}
        return await agent.run(payload)

    # ── Long-running queue worker ─────────────────────────────────────────

    async def run_forever(self) -> None:
        """Continuously claim and process queue items until stopped."""
        self._running = True
        self._build_dispatch_map()
        self.log.info("orchestrator_worker_started")

        stall_reaper_task = asyncio.create_task(self._stall_reaper_loop())

        try:
            while self._running:
                try:
                    processed = await self._process_one()
                except Exception as exc:
                    self.log.exception("process_one_error", error=str(exc))
                    processed = False
                if not processed:
                    await asyncio.sleep(_IDLE_SLEEP_SECONDS)
        finally:
            stall_reaper_task.cancel()
            self.log.info("orchestrator_worker_stopped")

    def stop(self) -> None:
        """Signal the worker to stop after the current item."""
        self._running = False

    async def _process_one(self) -> bool:
        """Claim one queue item, dispatch it, and mark complete/failed.

        Returns True if an item was processed, False if the queue was empty.
        """
        async with async_session_factory() as session:
            queue_repo = QueueRepository(session)
            item = await queue_repo.claim_one(agent_id="orchestrator")

            if item is None:
                return False

            item_id = item["id"]
            agent_name = item["agent_name"]
            payload = item.get("payload") or {}

        self.log.info("dispatching_queue_item", item_id=item_id, agent=agent_name)

        agent = self._get_agent(agent_name)
        if agent is None:
            self.log.error("unknown_agent", agent_name=agent_name, item_id=item_id)
            async with async_session_factory() as session:
                queue_repo = QueueRepository(session)
                await queue_repo.fail(
                    item_id, error=f"Unknown agent: {agent_name!r}", max_attempts=0
                )
                await session.commit()
            return True

        try:
            result = await agent.run(payload)
            async with async_session_factory() as session:
                queue_repo = QueueRepository(session)
                await queue_repo.complete(item_id, result=result)
                await session.commit()
            self.log.info("queue_item_complete", item_id=item_id, agent=agent_name)
        except Exception as exc:
            self.log.error(
                "queue_item_failed",
                item_id=item_id,
                agent=agent_name,
                error=str(exc),
            )
            async with async_session_factory() as session:
                queue_repo = QueueRepository(session)
                await queue_repo.fail(item_id, error=str(exc))
                await session.commit()

        return True

    async def _stall_reaper_loop(self) -> None:
        """Periodically reset stalled queue items so they can be retried."""
        while True:
            await asyncio.sleep(_STALL_REAPER_INTERVAL)
            try:
                async with async_session_factory() as session:
                    queue_repo = QueueRepository(session)
                    reset = await queue_repo.reset_stalled(stall_minutes=30)
                    await session.commit()
                if reset:
                    self.log.info("stalled_items_reset", count=reset)
            except Exception as exc:
                self.log.warning("stall_reaper_error", error=str(exc))

    # ── Agent dispatch ────────────────────────────────────────────────────

    def _build_dispatch_map(self) -> None:
        """Lazily import and cache agent singletons."""
        from aloha.agents.contact_research.agent import agent as contact_agent
        from aloha.agents.discovery.agent import agent as discovery_agent
        from aloha.agents.enrichment.agent import agent as enrichment_agent
        from aloha.agents.entity_research.agent import agent as entity_agent
        from aloha.agents.outreach.agent import agent as outreach_agent
        from aloha.agents.owner_research.agent import agent as owner_agent
        from aloha.agents.parcel_research.agent import agent as parcel_agent
        from aloha.agents.report.agent import agent as report_agent
        from aloha.agents.scoring.agent import agent as scoring_agent
        from aloha.agents.zoning.agent import agent as zoning_agent

        self._dispatch_map = {
            "discovery": discovery_agent,
            "parcel_research": parcel_agent,
            "owner_research": owner_agent,
            "entity_research": entity_agent,
            "contact_research": contact_agent,
            "enrichment": enrichment_agent,
            "scoring": scoring_agent,
            "report": report_agent,
            "outreach": outreach_agent,
            "zoning": zoning_agent,
        }

    def _get_agent(self, agent_name: str) -> BaseAgent | None:
        if not self._dispatch_map:
            self._build_dispatch_map()
        return self._dispatch_map.get(agent_name)


# ── Module-level singleton ─────────────────────────────────────────────────────

agent = OrchestratorAgent()
