"""Database Subagent — scheduled maintenance and automatic re-discovery.

Runs APScheduler jobs:
1. ``refresh_stale_parcels``  — every 6h: marks parcels older than N days as stale
   and re-enqueues them for parcel research
2. ``scheduled_discovery``   — daily: re-runs discovery for all registered counties
   that have active lien/deed data
3. ``cleanup_complete_queue``— weekly: deletes completed queue items older than 30d
4. ``reset_stalled_items``   — every 10min: resets processing items stuck > 30min

This agent is started alongside the Orchestrator in main.py lifespan.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog

from aloha.agents.base import BaseAgent
from aloha.db.engine import async_session_factory

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = structlog.get_logger().bind(agent="database")

# Counties to re-scan on schedule — extend as more scrapers are registered
_SCHEDULED_COUNTIES: list[tuple[str, str]] = [
    ("FL", "orange"),
    ("CO", "denver"),
    ("IA", "polk"),
]


class DatabaseAgent(BaseAgent):
    """Scheduled maintenance jobs for the research database.

    Context keys for ``run(context)`` (one-shot manual trigger):
    - ``task``: one of 'refresh_stale', 'discovery', 'cleanup', 'reset_stalled'
    """

    def __init__(self) -> None:
        super().__init__(name="database")
        self._scheduler: AsyncIOScheduler | None = None

    def get_tools(self) -> list[dict[str, Any]]:
        return []

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """One-shot task runner (used by orchestrator queue dispatch)."""
        task = context.get("task", "refresh_stale")
        if task == "refresh_stale":
            count = await self.refresh_stale_parcels()
            return {"status": "complete", "task": task, "count": count}
        if task == "discovery":
            count = await self.scheduled_discovery()
            return {"status": "complete", "task": task, "count": count}
        if task == "cleanup":
            count = await self.cleanup_complete_queue()
            return {"status": "complete", "task": task, "count": count}
        if task == "reset_stalled":
            count = await self.reset_stalled_items()
            return {"status": "complete", "task": task, "count": count}
        return {"status": "error", "reason": f"Unknown task: {task!r}"}

    # ── Scheduled tasks ───────────────────────────────────────────────────

    async def refresh_stale_parcels(self, stale_after_days: int = 14) -> int:
        """Mark parcels not crawled in N days as stale and re-enqueue."""
        from sqlalchemy import select

        from aloha.db.models.parcel import Parcel
        from aloha.db.repositories import ParcelRepository, QueueRepository

        older_than_hours = stale_after_days * 24

        async with async_session_factory() as session:
            parcel_repo = ParcelRepository(session)
            queue_repo = QueueRepository(session)

            # Query parcels that will be marked stale (before marking)
            cutoff = datetime.now(tz=UTC) - timedelta(hours=older_than_hours)
            stmt = select(Parcel).where(
                Parcel.data_freshness == "fresh",
                Parcel.last_crawled_at < cutoff,
            )
            result = await session.execute(stmt)
            stale = list(result.scalars().all())

            # Mark them stale via repository
            await parcel_repo.mark_stale(older_than_hours=older_than_hours)

            # Re-enqueue stale parcels for parcel research
            for parcel in stale:
                await queue_repo.enqueue(
                    agent_name="parcel_research",
                    stage="parcel",
                    parcel_id=parcel.parcel_id,
                    payload={
                        "parcel_id": parcel.parcel_id,
                        "state": parcel.state,
                        "county": parcel.county,
                        "address": parcel.address,
                    },
                    priority=3,
                )
            await session.commit()

        count = len(stale)
        log.info("stale_parcels_refreshed", count=count, stale_after_days=stale_after_days)
        return count

    async def scheduled_discovery(self) -> int:
        """Re-run discovery for all registered county/state pairs."""
        from aloha.agents.discovery.agent import agent as discovery_agent

        total = 0
        for state, county in _SCHEDULED_COUNTIES:
            try:
                result = await discovery_agent.run(
                    {
                        "state": state,
                        "county": county,
                        "max_records": 5000,
                    }
                )
                enqueued = result.get("enqueued", 0)
                total += enqueued
                log.info("scheduled_discovery_done", state=state, county=county, enqueued=enqueued)
            except Exception as exc:
                log.warning(
                    "scheduled_discovery_failed", state=state, county=county, error=str(exc)
                )

        return total

    async def cleanup_complete_queue(self, older_than_days: int = 30) -> int:
        """Delete completed/failed queue items older than N days."""
        cutoff = datetime.now(tz=UTC) - timedelta(days=older_than_days)
        from sqlalchemy import delete

        from aloha.db.models.queue_item import QueueItem

        async with async_session_factory() as session:
            result = await session.execute(
                delete(QueueItem).where(
                    QueueItem.status.in_(["complete", "failed"]),
                    QueueItem.created_at < cutoff,
                )
            )
            await session.commit()
            deleted: int = result.rowcount or 0

        log.info("queue_cleanup_done", deleted=deleted, older_than_days=older_than_days)
        return deleted

    async def reset_stalled_items(self, stall_minutes: int = 30) -> int:
        """Reset queue items stuck in 'processing' state."""
        from aloha.db.repositories import QueueRepository

        async with async_session_factory() as session:
            queue_repo = QueueRepository(session)
            reset = await queue_repo.reset_stalled(
                stalled_after_minutes=stall_minutes,
            )
            await session.commit()

        if reset:
            log.info("stalled_items_reset", count=reset)
        return reset or 0

    # ── Scheduler lifecycle ───────────────────────────────────────────────

    def start_scheduler(self) -> None:
        """Start the APScheduler background scheduler."""
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger
            from apscheduler.triggers.interval import IntervalTrigger
        except ImportError:
            log.warning("apscheduler_not_installed", note="pip install apscheduler")
            return

        self._scheduler = AsyncIOScheduler()

        # Stale parcel refresh — every 6 hours
        self._scheduler.add_job(
            self.refresh_stale_parcels,
            trigger=IntervalTrigger(hours=6),
            id="refresh_stale",
            name="Refresh stale parcels",
            replace_existing=True,
        )

        # Discovery re-scan — daily at 02:00 UTC
        self._scheduler.add_job(
            self.scheduled_discovery,
            trigger=CronTrigger(hour=2, minute=0),
            id="scheduled_discovery",
            name="Scheduled county discovery",
            replace_existing=True,
        )

        # Queue cleanup — weekly on Sunday at 03:00 UTC
        self._scheduler.add_job(
            self.cleanup_complete_queue,
            trigger=CronTrigger(day_of_week="sun", hour=3, minute=0),
            id="queue_cleanup",
            name="Clean completed queue items",
            replace_existing=True,
        )

        # Stalled item reaper — every 10 minutes
        self._scheduler.add_job(
            self.reset_stalled_items,
            trigger=IntervalTrigger(minutes=10),
            id="stall_reaper",
            name="Reset stalled queue items",
            replace_existing=True,
        )

        self._scheduler.start()
        log.info("database_scheduler_started", jobs=len(self._scheduler.get_jobs()))

    def stop_scheduler(self) -> None:
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            log.info("database_scheduler_stopped")


# ── Module-level singleton ─────────────────────────────────────────────────────

agent = DatabaseAgent()
