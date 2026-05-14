"""PostgreSQL SKIP LOCKED queue runner (Phase 1).

Polls the ``queue_items`` table for unclaimed work, dispatches each item to
the appropriate agent, and marks the row complete or failed.
"""

from __future__ import annotations

import asyncio
import importlib
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from aloha.agents import AGENT_REGISTRY
from aloha.db.engine import async_session_factory

log: structlog.stdlib.BoundLogger = structlog.get_logger().bind(component="queue_runner")

# ── SQL fragments ─────────────────────────────────────────────────────────

CLAIM_SQL = text("""
    UPDATE queue_items
       SET status   = 'processing',
           claimed_at = now()
     WHERE id = (
         SELECT id
           FROM queue_items
          WHERE status = 'pending'
          ORDER BY priority DESC, created_at ASC
            FOR UPDATE SKIP LOCKED
          LIMIT 1
     )
     RETURNING id, agent_name, payload
""")

COMPLETE_SQL = text("""
    UPDATE queue_items
       SET status       = :status,
           completed_at = now(),
           result       = :result
     WHERE id = :item_id
""")


async def _resolve_agent(agent_name: str) -> Any:
    """Dynamically import and return the agent instance.

    Args:
        agent_name: Key in ``AGENT_REGISTRY`` (e.g. ``"parcel_research"``).

    Returns:
        An instantiated agent object.
    """
    module_path = AGENT_REGISTRY.get(agent_name)
    if module_path is None:
        raise ValueError(f"Unknown agent: {agent_name!r}")

    module = importlib.import_module(module_path)
    # Convention: each agent module exposes an ``agent`` attribute.
    return getattr(module, "agent")


async def process_one(session: AsyncSession) -> bool:
    """Claim and process a single queue item.

    Returns:
        ``True`` if an item was processed, ``False`` if the queue was empty.
    """
    result = await session.execute(CLAIM_SQL)
    row = result.mappings().first()

    if row is None:
        return False

    item_id: int = row["id"]
    agent_name: str = row["agent_name"]
    payload: dict[str, Any] = row["payload"] or {}

    log.info("processing_item", item_id=item_id, agent=agent_name)

    try:
        agent = await _resolve_agent(agent_name)
        agent_result = await agent.run(payload)
        await session.execute(
            COMPLETE_SQL,
            {"item_id": item_id, "status": "complete", "result": str(agent_result)},
        )
        await session.commit()
        log.info("item_complete", item_id=item_id)
    except Exception as exc:
        # Catch-all: agent processing can fail in arbitrary ways; record
        # the failure in the DB so the item is not retried endlessly.
        await session.rollback()
        async with async_session_factory() as err_session:
            await err_session.execute(
                COMPLETE_SQL,
                {"item_id": item_id, "status": "failed", "result": str(exc)},
            )
            await err_session.commit()
        log.error("item_failed", item_id=item_id, error=str(exc), exc_info=True)

    return True


async def run_loop(*, poll_interval: float = 2.0) -> None:
    """Continuously poll for queue items until cancelled.

    Args:
        poll_interval: Seconds to sleep when the queue is empty.
    """
    log.info("queue_runner_started", poll_interval=poll_interval)

    while True:
        try:
            async with async_session_factory() as session:
                found = await process_one(session)
            if not found:
                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            log.info("queue_runner_stopped")
            break
        except Exception as exc:
            # Catch-all: top-level error boundary for the queue runner loop
            log.error("queue_runner_error", error=str(exc), exc_info=True)
            await asyncio.sleep(poll_interval)
