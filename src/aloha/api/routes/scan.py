"""Scan / queue / status API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from aloha.api.deps import get_current_user, get_db
from aloha.api.schemas.parcels import QueueStatusOut, ScanRequest, ScanResponse
from aloha.services.billing_service import BillingService
from aloha.services.research_service import ResearchService

router = APIRouter(tags=["scan"])


def _research_service(db: AsyncSession = Depends(get_db)) -> ResearchService:
    billing = BillingService(db)
    return ResearchService(db, billing)


@router.post("/run", response_model=ScanResponse)
async def trigger_scan(
    body: ScanRequest,
    background_tasks: BackgroundTasks,
    svc: ResearchService = Depends(_research_service),
    user: Annotated[None, Depends(get_current_user)] = None,
) -> ScanResponse:
    """Trigger a new tax lien/deed discovery scan for a state/county.

    Validates quota, then runs the Discovery Agent in the background.
    """
    user_id = str(user.id) if user else "anonymous"
    tier = user.tier if user else "free"

    result = await svc.trigger_scan(
        user_id=user_id,
        tier=tier,
        state=body.state,
        county=body.county,
        instrument_filter=body.instrument_filter,
        max_records=body.max_records,
    )

    # Still run the discovery agent as a background task
    background_tasks.add_task(
        _run_discovery,
        state=body.state,
        county=body.county,
        instrument_filter=body.instrument_filter,
        max_records=body.max_records,
        user_id=user_id,
    )
    return result


async def _run_discovery(
    *,
    state: str,
    county: str,
    instrument_filter: str | None,
    max_records: int,
    user_id: str | None = None,
) -> None:
    """Background task — run the Discovery Agent."""
    from aloha.agents.discovery.agent import agent as discovery_agent

    context = {
        "state": state,
        "county": county,
        "instrument_filter": instrument_filter,
        "max_records": max_records,
        "user_id": user_id,
    }
    try:
        await discovery_agent.run(context)
    except Exception:
        # Catch-all: top-level error boundary for background discovery task
        import structlog
        log = structlog.get_logger()
        log.exception("discovery_background_failed", state=state, county=county)


@router.get("/queue/status", response_model=QueueStatusOut)
async def queue_status(
    svc: ResearchService = Depends(_research_service),
    _user: Annotated[None, Depends(get_current_user)] = None,
) -> QueueStatusOut:
    """Return current queue depth by status."""
    return await svc.get_queue_status()
