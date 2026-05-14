"""Research service — scan triggers, queue management, quota validation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from aloha.api.schemas.parcels import QueueStatusOut, ScanResponse
from aloha.db.models.parcel import Parcel
from aloha.db.models.queue_item import QueueItem
from aloha.services.base import BaseService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from aloha.services.billing_service import BillingService


class ResearchService(BaseService):
    """Orchestrates scan triggers and research pipeline status."""

    def __init__(
        self,
        session: AsyncSession,
        billing_service: BillingService,
    ) -> None:
        super().__init__(session)
        self._billing = billing_service

    # ── Public API ───────────────────────────────────────────────────────

    async def trigger_scan(
        self,
        *,
        user_id: str,
        tier: str,
        state: str,
        county: str,
        instrument_filter: str | None = None,
        max_records: int = 5000,
    ) -> ScanResponse:
        """Validate quota and trigger a discovery scan.

        Raises QuotaExceededError if the user has exceeded their tier limit.
        """
        await self._billing.check_quota(user_id, tier)

        self.log.info(
            "scan_triggered",
            user_id=user_id,
            state=state,
            county=county,
            instrument_filter=instrument_filter,
        )

        return ScanResponse(
            status="queued",
            state=state.upper(),
            county=county.lower(),
            message=f"Discovery scan queued for {state.upper()}/{county.lower()}",
        )

    async def get_queue_status(self, user_id: str | None = None) -> QueueStatusOut:
        """Return current queue depth by status."""
        result = await self._session.execute(
            select(QueueItem.status, func.count().label("cnt")).group_by(QueueItem.status),
        )
        counts = {row.status: row.cnt for row in result}

        agent_result = await self._session.execute(
            select(QueueItem.agent_name, func.count().label("cnt"))
            .where(QueueItem.status == "pending")
            .group_by(QueueItem.agent_name),
        )
        agents = {row.agent_name: row.cnt for row in agent_result}

        return QueueStatusOut(
            pending=counts.get("pending", 0),
            processing=counts.get("processing", 0),
            failed=counts.get("failed", 0),
            complete=counts.get("complete", 0),
            agents=agents,
        )

    async def get_parcel_research_status(self, parcel_id: str) -> dict:
        """Return current research pipeline status for a parcel."""
        parcel = await self._session.get(Parcel, parcel_id)
        if parcel is None:
            return {"parcel_id": parcel_id, "status": "not_found"}

        # Get pending/processing queue items for this parcel
        result = await self._session.execute(
            select(QueueItem.agent_name, QueueItem.status).where(
                QueueItem.parcel_id == parcel_id,
                QueueItem.status.in_(["pending", "processing"]),
            ),
        )
        active_items = [{"agent": row.agent_name, "status": row.status} for row in result]

        return {
            "parcel_id": parcel_id,
            "research_status": parcel.research_status,
            "active_queue_items": active_items,
        }

    async def enqueue_next_stage(
        self,
        parcel_id: str,
        current_stage: str,
        user_id: str | None = None,
    ) -> None:
        """Enqueue the next pipeline stage for a parcel."""
        stage_order = [
            "discover",
            "parcel",
            "owner",
            "entity",
            "contact",
            "enrich",
            "score",
        ]
        try:
            idx = stage_order.index(current_stage)
        except ValueError:
            self.log.warning("unknown_stage", stage=current_stage, parcel_id=parcel_id)
            return

        if idx + 1 >= len(stage_order):
            self.log.info("pipeline_complete", parcel_id=parcel_id)
            return

        next_stage = stage_order[idx + 1]
        payload = {"user_id": user_id} if user_id else None
        item = QueueItem(
            parcel_id=parcel_id,
            agent_name=next_stage,
            stage=next_stage,
            priority=5,
            status="pending",
            payload=payload,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        self._session.add(item)
        await self._session.flush()
        self.log.info("stage_enqueued", parcel_id=parcel_id, next_stage=next_stage)
