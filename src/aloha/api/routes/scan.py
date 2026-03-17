"""Scan / queue / status API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from aloha.api.deps import get_current_user, get_db
from aloha.api.schemas.parcels import QueueStatusOut, ScanRequest, ScanResponse
from aloha.db.models.queue_item import QueueItem

router = APIRouter(tags=["scan"])


@router.post("/run", response_model=ScanResponse)
async def trigger_scan(
    body: ScanRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _user: Annotated[None, Depends(get_current_user)] = None,
) -> ScanResponse:
    """Trigger a new tax lien/deed discovery scan for a state/county.

    Runs the Discovery Agent in the background and returns immediately.
    """
    background_tasks.add_task(
        _run_discovery,
        state=body.state,
        county=body.county,
        instrument_filter=body.instrument_filter,
        max_records=body.max_records,
    )
    return ScanResponse(
        status="queued",
        state=body.state.upper(),
        county=body.county.lower(),
        message=f"Discovery scan queued for {body.state.upper()}/{body.county.lower()}",
    )


async def _run_discovery(
    *,
    state: str,
    county: str,
    instrument_filter: str | None,
    max_records: int,
) -> None:
    """Background task — run the Discovery Agent."""
    from aloha.agents.discovery.agent import agent as discovery_agent

    context = {
        "state": state,
        "county": county,
        "instrument_filter": instrument_filter,
        "max_records": max_records,
    }
    try:
        await discovery_agent.run(context)
    except Exception:
        import structlog
        log = structlog.get_logger()
        log.exception("discovery_background_failed", state=state, county=county)


@router.get("/queue/status", response_model=QueueStatusOut)
async def queue_status(
    db: AsyncSession = Depends(get_db),
    _user: Annotated[None, Depends(get_current_user)] = None,
) -> QueueStatusOut:
    """Return current queue depth by status."""
    result = await db.execute(
        select(QueueItem.status, func.count().label("cnt"))
        .group_by(QueueItem.status)
    )
    counts = {row.status: row.cnt for row in result}

    # Per-agent pending breakdown
    agent_result = await db.execute(
        select(QueueItem.agent_name, func.count().label("cnt"))
        .where(QueueItem.status == "pending")
        .group_by(QueueItem.agent_name)
    )
    agents = {row.agent_name: row.cnt for row in agent_result}

    return QueueStatusOut(
        pending=counts.get("pending", 0),
        processing=counts.get("processing", 0),
        failed=counts.get("failed", 0),
        complete=counts.get("complete", 0),
        agents=agents,
    )
