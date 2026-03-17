"""Opportunity score model — instrument-aware scoring results."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ARRAY, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aloha.db.models.base import Base


class Score(Base):
    """Scored investment opportunity for a parcel.

    Lien certificate and tax deed records have separate factor columns;
    only the columns relevant to ``instrument_type`` are populated.
    """

    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parcel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("parcels.parcel_id", ondelete="CASCADE"), nullable=False, index=True
    )
    instrument_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # lien_certificate | tax_deed

    overall_score: Mapped[int | None] = mapped_column(Integer)  # 0-100
    score_model_version: Mapped[str | None] = mapped_column(String(30))
    # e.g. 'lien_v1', 'deed_v1'

    # Shared factors (0-10)
    property_potential: Mapped[int | None] = mapped_column(Integer)
    risk_score: Mapped[int | None] = mapped_column(Integer)

    # ── Lien Certificate factors (null for tax deed records) ──────────────
    lien_to_value_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4))
    certificate_rate: Mapped[float | None] = mapped_column(Numeric(6, 4))
    years_delinquent: Mapped[int | None] = mapped_column(Integer)
    owner_motivation: Mapped[int | None] = mapped_column(Integer)       # 0-10
    contact_reachability: Mapped[int | None] = mapped_column(Integer)   # 0-10
    redemption_urgency: Mapped[int | None] = mapped_column(Integer)     # 0-10

    # ── Tax Deed factors (null for lien certificate records) ──────────────
    arv_estimate: Mapped[float | None] = mapped_column(Numeric(14, 2))
    opening_bid: Mapped[float | None] = mapped_column(Numeric(14, 2))
    arv_to_bid_ratio: Mapped[float | None] = mapped_column(Numeric(8, 2))
    title_clarity: Mapped[int | None] = mapped_column(Integer)          # 0-10
    condition_risk: Mapped[int | None] = mapped_column(Integer)         # 0-10
    competition_risk: Mapped[int | None] = mapped_column(Integer)       # 0-10
    post_sale_redemption_risk: Mapped[int | None] = mapped_column(Integer)  # 0-10

    # Output
    risk_flags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    flags_detail: Mapped[dict | None] = mapped_column(JSONB)
    score_rationale: Mapped[str | None] = mapped_column(Text)
    scored_at: Mapped[datetime] = mapped_column(nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────
    parcel: Mapped["Parcel"] = relationship("Parcel", back_populates="scores", lazy="raise")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<Score id={self.id} parcel={self.parcel_id!r} "
            f"type={self.instrument_type!r} score={self.overall_score}>"
        )
