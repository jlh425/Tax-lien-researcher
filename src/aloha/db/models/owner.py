"""Owner and entity ORM models."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aloha.db.models.base import Base, TimestampMixin


class Owner(Base, TimestampMixin):
    """Owner of record for a parcel, as found in public records."""

    __tablename__ = "owners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parcel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("parcels.parcel_id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Owner of record (exactly as on deed)
    owner_of_record: Mapped[str | None] = mapped_column(Text)
    owner_type: Mapped[str | None] = mapped_column(String(30))
    # individual|llc|trust|corporation|government|unknown

    # Mailing address
    mailing_address: Mapped[str | None] = mapped_column(Text)
    mailing_city: Mapped[str | None] = mapped_column(String(100))
    mailing_state: Mapped[str | None] = mapped_column(String(2))
    mailing_zip: Mapped[str | None] = mapped_column(String(10))
    is_absentee: Mapped[bool | None] = mapped_column(Boolean)

    # Deed info
    deed_type: Mapped[str | None] = mapped_column(String(50))  # warranty|quitclaim|trust|grant
    acquisition_date: Mapped[date | None] = mapped_column(Date)
    acquisition_price: Mapped[int | None] = mapped_column(Integer)

    # Beneficial owner (pierced through entity)
    beneficial_owner: Mapped[str | None] = mapped_column(Text)
    beneficial_owner_confidence: Mapped[str | None] = mapped_column(String(20))
    # high|medium|low|unknown

    # Best contact info found
    best_phone: Mapped[str | None] = mapped_column(String(30))
    best_email: Mapped[str | None] = mapped_column(String(255))
    best_contact_address: Mapped[str | None] = mapped_column(Text)

    # Research depth completed (1-5 levels)
    research_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sources: Mapped[dict | None] = mapped_column(JSONB)

    # ── Relationships ─────────────────────────────────────────────────────
    parcel: Mapped["Parcel"] = relationship("Parcel", back_populates="owners", lazy="raise")  # noqa: F821
    entity_links: Mapped[list["OwnerEntity"]] = relationship(
        "OwnerEntity", back_populates="owner", cascade="all, delete-orphan", lazy="raise"
    )
    outreach_logs: Mapped[list["OutreachLog"]] = relationship(  # noqa: F821
        "OutreachLog", back_populates="owner", lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<Owner id={self.id} parcel={self.parcel_id!r} name={self.owner_of_record!r}>"


class Entity(Base):
    """A business entity (LLC, corp, trust) that may own one or more parcels."""

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_name: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    # llc|corporation|trust|partnership|nonprofit
    state_of_formation: Mapped[str | None] = mapped_column(String(2))
    sos_status: Mapped[str | None] = mapped_column(String(30))
    # active|dissolved|revoked|suspended
    formation_date: Mapped[date | None] = mapped_column(Date)
    registered_agent: Mapped[str | None] = mapped_column(Text)
    registered_agent_address: Mapped[str | None] = mapped_column(Text)
    officers: Mapped[dict | None] = mapped_column(JSONB)       # [{name, title}]
    managers_members: Mapped[dict | None] = mapped_column(JSONB)
    sos_filing_url: Mapped[str | None] = mapped_column(Text)

    # Related entities (same manager/address)
    related_entity_ids: Mapped[list | None] = mapped_column(JSONB)

    # Financials
    ucc_filings: Mapped[dict | None] = mapped_column(JSONB)
    federal_tax_liens: Mapped[dict | None] = mapped_column(JSONB)
    state_tax_liens: Mapped[dict | None] = mapped_column(JSONB)
    bankruptcy_history: Mapped[dict | None] = mapped_column(JSONB)

    # Litigation
    litigation_summary: Mapped[str | None] = mapped_column(Text)
    pacer_results: Mapped[dict | None] = mapped_column(JSONB)

    # Contact
    website: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))

    # Change detection
    content_hash: Mapped[str | None] = mapped_column(String(64))
    last_researched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────
    owner_links: Mapped[list["OwnerEntity"]] = relationship(
        "OwnerEntity", back_populates="entity", cascade="all, delete-orphan", lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<Entity id={self.id} name={self.entity_name!r} type={self.entity_type!r}>"


class OwnerEntity(Base):
    """Many-to-many link between Owner and Entity records."""

    __tablename__ = "owner_entities"

    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("owners.id", ondelete="CASCADE"), primary_key=True
    )
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True
    )

    owner: Mapped["Owner"] = relationship("Owner", back_populates="entity_links", lazy="raise")
    entity: Mapped["Entity"] = relationship("Entity", back_populates="owner_links", lazy="raise")
