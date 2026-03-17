"""Alert model — deadline and status-change notifications."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aloha.db.models.base import Base


class Alert(Base):
    """A notification queued for delivery to the user.

    The Database Subagent creates alerts; the Notification service sends them.
    """

    __tablename__ = "alerts"
    __table_args__ = (
        Index("idx_alerts_unsent", "alert_date", postgresql_where="sent = FALSE"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parcel_id: Mapped[str | None] = mapped_column(
        String(100), ForeignKey("parcels.parcel_id", ondelete="CASCADE"), index=True
    )
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # redemption_deadline|auction_date|lien_status_change|new_high_score
    alert_date: Mapped[date | None] = mapped_column(Date)
    message: Mapped[str | None] = mapped_column(Text)
    sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────
    parcel: Mapped["Parcel | None"] = relationship(  # noqa: F821
        "Parcel", back_populates="alerts", lazy="raise"
    )

    def __repr__(self) -> str:
        return (
            f"<Alert id={self.id} type={self.alert_type!r} "
            f"parcel={self.parcel_id!r} sent={self.sent}>"
        )
