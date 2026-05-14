"""Parcel ORM model — core property record."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aloha.db.models.base import Base, TimestampMixin


class Parcel(Base, TimestampMixin):
    """A land parcel that may have a tax lien or deed auction pending."""

    __tablename__ = "parcels"

    parcel_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    # Location
    county: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(Text)
    address_normalized: Mapped[str | None] = mapped_column(Text)  # USPS-standard form
    legal_description: Mapped[str | None] = mapped_column(Text)

    # Property characteristics
    acreage: Mapped[float | None] = mapped_column(Numeric(12, 4))
    land_use_code: Mapped[str | None] = mapped_column(String(50))
    property_type: Mapped[str | None] = mapped_column(String(50))
    # residential|commercial|land|industrial|agricultural
    zoning: Mapped[str | None] = mapped_column(String(50))
    zoning_notes: Mapped[str | None] = mapped_column(Text)

    # Valuation
    assessed_land_val: Mapped[int | None] = mapped_column(Integer)
    assessed_impr_val: Mapped[int | None] = mapped_column(Integer)
    assessed_total: Mapped[int | None] = mapped_column(Integer)
    market_value_est: Mapped[int | None] = mapped_column(Integer)
    last_sale_date: Mapped[date | None] = mapped_column(Date)
    last_sale_price: Mapped[int | None] = mapped_column(Integer)
    year_built: Mapped[int | None] = mapped_column(Integer)

    # Geolocation (populated during parcel research)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))

    # Research pipeline state
    research_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="discovered", index=True
    )
    # discovered|parcel_researched|owner_researched|enriched|scored|complete
    data_freshness: Mapped[str] = mapped_column(String(20), nullable=False, default="fresh")
    # fresh|stale|expired
    content_hash: Mapped[str | None] = mapped_column(String(64))
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── Relationships ─────────────────────────────────────────────────────
    user: Mapped[User] = relationship("User", back_populates="parcels", lazy="raise")  # noqa: F821
    tax_liens: Mapped[list[TaxLien]] = relationship(  # noqa: F821
        "TaxLien", back_populates="parcel", cascade="all, delete-orphan", lazy="raise"
    )
    owners: Mapped[list[Owner]] = relationship(  # noqa: F821
        "Owner", back_populates="parcel", cascade="all, delete-orphan", lazy="raise"
    )
    scores: Mapped[list[Score]] = relationship(  # noqa: F821
        "Score", back_populates="parcel", cascade="all, delete-orphan", lazy="raise"
    )
    property_images: Mapped[list[PropertyImage]] = relationship(  # noqa: F821
        "PropertyImage", back_populates="parcel", cascade="all, delete-orphan", lazy="raise"
    )
    source_screenshots: Mapped[list[SourceScreenshot]] = relationship(  # noqa: F821
        "SourceScreenshot", back_populates="parcel", cascade="all, delete-orphan", lazy="raise"
    )
    alerts: Mapped[list[Alert]] = relationship(  # noqa: F821
        "Alert", back_populates="parcel", cascade="all, delete-orphan", lazy="raise"
    )
    document_chunks: Mapped[list[DocumentChunk]] = relationship(  # noqa: F821
        "DocumentChunk", back_populates="parcel", cascade="all, delete-orphan", lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<Parcel id={self.parcel_id!r} state={self.state!r} county={self.county!r}>"
