"""Research queue model — SKIP LOCKED job table."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aloha.db.models.base import Base


class QueueItem(Base):
    """A unit of work in the research pipeline.

    Agents claim rows using ``FOR UPDATE SKIP LOCKED`` to prevent duplicate
    processing across concurrent workers.
    """

    __tablename__ = "queue_items"
    __table_args__ = (
        Index(
            "idx_queue_pickup",
            "status",
            "priority",
            "next_retry_at",
            postgresql_where="status IN ('pending', 'retry')",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parcel_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("parcels.parcel_id", ondelete="CASCADE"),
        index=True,
        nullable=True,  # Some queue items (e.g. discovery) are not tied to a parcel yet
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # discover|parcel|owner|entity|contact|enrich|score|outreach
    stage: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    # 1=urgent (deadline <30d), 10=low
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    # pending|processing|complete|failed|retry|skipped
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_by: Mapped[str | None] = mapped_column(String(100))   # agent instance ID
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict | None] = mapped_column(JSONB)            # arbitrary task context
    result: Mapped[dict | None] = mapped_column(JSONB)             # agent output summary
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<QueueItem id={self.id} agent={self.agent_name!r} "
            f"status={self.status!r} priority={self.priority}>"
        )
