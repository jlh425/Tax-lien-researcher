"""Queue repository — claim, complete, and manage research queue items."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, text, update

from aloha.db.models.queue_item import QueueItem

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

# ── SQL for atomic SKIP LOCKED claim ──────────────────────────────────────────
# Two variants: asyncpg cannot infer type for NULL parameters used in both
# IS NULL and = comparisons, so we use separate queries.
_CLAIM_SQL_ANY = text("""
    UPDATE queue_items
       SET status     = 'processing',
           claimed_by  = :agent_id,
           claimed_at  = now(),
           updated_at  = now()
     WHERE id = (
         SELECT id
           FROM queue_items
          WHERE status IN ('pending', 'retry')
            AND (next_retry_at IS NULL OR next_retry_at <= now())
          ORDER BY priority ASC, created_at ASC
            FOR UPDATE SKIP LOCKED
          LIMIT 1
     )
     RETURNING id, parcel_id, agent_name, stage, payload, attempts
""")

_CLAIM_SQL_NAMED = text("""
    UPDATE queue_items
       SET status     = 'processing',
           claimed_by  = :agent_id,
           claimed_at  = now(),
           updated_at  = now()
     WHERE id = (
         SELECT id
           FROM queue_items
          WHERE status IN ('pending', 'retry')
            AND (next_retry_at IS NULL OR next_retry_at <= now())
            AND agent_name = :agent_name
          ORDER BY priority ASC, created_at ASC
            FOR UPDATE SKIP LOCKED
          LIMIT 1
     )
     RETURNING id, parcel_id, agent_name, stage, payload, attempts
""")


class QueueRepository:
    """Data-access layer for the research queue."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(
        self,
        *,
        agent_name: str,
        stage: str,
        parcel_id: str | None = None,
        payload: dict[str, Any] | None = None,
        priority: int = 5,
    ) -> QueueItem:
        """Add a new job to the queue."""
        now = datetime.now(tz=UTC)
        item = QueueItem(
            parcel_id=parcel_id,
            agent_name=agent_name,
            stage=stage,
            priority=priority,
            status="pending",
            payload=payload or {},
            created_at=now,
            updated_at=now,
        )
        self._session.add(item)
        await self._session.flush()
        return item

    async def claim_one(
        self,
        *,
        agent_id: str,
        agent_name: str | None = None,
    ) -> dict[str, Any] | None:
        """Atomically claim the next available queue item.

        Returns the row mapping if a job was claimed, ``None`` if queue empty.
        """
        if agent_name is not None:
            result = await self._session.execute(
                _CLAIM_SQL_NAMED,
                {"agent_id": agent_id, "agent_name": agent_name},
            )
        else:
            result = await self._session.execute(
                _CLAIM_SQL_ANY,
                {"agent_id": agent_id},
            )
        row = result.mappings().first()
        return dict(row) if row else None

    async def complete(self, item_id: int, *, result: dict[str, Any] | None = None) -> None:
        """Mark a queue item as successfully completed."""
        await self._session.execute(
            update(QueueItem)
            .where(QueueItem.id == item_id)
            .values(
                status="complete",
                result=_sanitize_for_json(result),
                completed_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )
        )

    async def fail(
        self,
        item_id: int,
        *,
        error: str,
        retry_after_seconds: int = 60,
        max_attempts: int = 3,
    ) -> None:
        """Mark a queue item as failed; schedule retry if attempts remain."""
        item = await self._session.get(QueueItem, item_id)
        if item is None:
            return

        new_attempts = item.attempts + 1
        if new_attempts >= max_attempts:
            new_status = "failed"
            next_retry = None
        else:
            new_status = "retry"
            backoff = retry_after_seconds * (2 ** (new_attempts - 1))
            next_retry = datetime.now(tz=UTC) + timedelta(seconds=backoff)

        await self._session.execute(
            update(QueueItem)
            .where(QueueItem.id == item_id)
            .values(
                status=new_status,
                attempts=new_attempts,
                last_error=error,
                next_retry_at=next_retry,
                updated_at=datetime.now(tz=UTC),
            )
        )

    async def get_pending_count(self, agent_name: str | None = None) -> int:
        """Count pending + retry items, optionally filtered by agent."""
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(QueueItem)
            .where(QueueItem.status.in_(["pending", "retry"]))
        )
        if agent_name:
            stmt = stmt.where(QueueItem.agent_name == agent_name)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_stalled(self, stalled_after_minutes: int = 60) -> Sequence[QueueItem]:
        """Return processing items that haven't moved in ``stalled_after_minutes``."""
        cutoff = datetime.now(tz=UTC) - timedelta(minutes=stalled_after_minutes)
        stmt = select(QueueItem).where(
            QueueItem.status == "processing",
            QueueItem.claimed_at < cutoff,
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def reset_stalled(self, stalled_after_minutes: int = 60) -> int:
        """Reset stalled processing items back to 'pending' for retry."""
        cutoff = datetime.now(tz=UTC) - timedelta(minutes=stalled_after_minutes)
        result = await self._session.execute(
            update(QueueItem)
            .where(
                QueueItem.status == "processing",
                QueueItem.claimed_at < cutoff,
            )
            .values(
                status="pending",
                claimed_by=None,
                claimed_at=None,
                updated_at=datetime.now(tz=UTC),
            )
        )
        return result.rowcount or 0


def _sanitize_for_json(obj: Any) -> Any:
    """Convert Decimal and other non-JSON-native types for JSONB storage."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, Decimal):
        return float(obj)
    return obj
