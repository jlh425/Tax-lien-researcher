"""TaxLien ORM model — covers both lien certificates and tax deed auctions."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aloha.db.models.base import Base


class TaxLien(Base):
    """A tax lien certificate or tax deed auction record.

    ``instrument_type`` drives which fields are populated and which scoring
    model is applied downstream.
    """

    __tablename__ = "tax_liens"
    __table_args__ = (
        UniqueConstraint("parcel_id", "tax_year", "certificate_number", name="uq_lien_cert"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parcel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("parcels.parcel_id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Instrument classification — drives scoring model
    instrument_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="lien_certificate", index=True
    )
    # lien_certificate | tax_deed | hybrid_pending

    # Shared fields
    lien_status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)
    tax_year: Mapped[int | None] = mapped_column(Integer)
    years_delinquent: Mapped[int | None] = mapped_column(Integer)
    principal_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    interest_amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    penalty_amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    total_owed: Mapped[float | None] = mapped_column(Numeric(14, 2))
    filing_date: Mapped[date | None] = mapped_column(Date)

    # Lien Certificate specific
    redemption_deadline: Mapped[date | None] = mapped_column(Date, index=True)
    certificate_number: Mapped[str | None] = mapped_column(String(100))
    certificate_interest_rate: Mapped[float | None] = mapped_column(Numeric(6, 4))
    lien_holder: Mapped[str] = mapped_column(String(255), nullable=False, default="county")

    # Tax Deed specific
    auction_date: Mapped[date | None] = mapped_column(Date, index=True)
    auction_time: Mapped[str | None] = mapped_column(String(50))
    auction_platform: Mapped[str | None] = mapped_column(String(100))
    # courthouse_steps|bid4assets|realauction|govease|sri|lgbs|lienhub|county_online
    auction_url: Mapped[str | None] = mapped_column(Text)
    opening_bid: Mapped[float | None] = mapped_column(Numeric(14, 2))
    post_sale_redemption_days: Mapped[int | None] = mapped_column(Integer)
    title_encumbrances: Mapped[dict | None] = mapped_column(JSONB)
    title_risk_level: Mapped[str | None] = mapped_column(String(30))
    # clear|minor|significant|clouded

    # Source tracking
    source_url: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── Relationships ─────────────────────────────────────────────────────
    parcel: Mapped["Parcel"] = relationship("Parcel", back_populates="tax_liens", lazy="raise")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<TaxLien id={self.id} parcel={self.parcel_id!r} "
            f"type={self.instrument_type!r} status={self.lien_status!r}>"
        )
