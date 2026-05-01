"""Outreach models — log, do-not-contact list, and templates."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import ARRAY, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aloha.db.models.base import Base


class OutreachLog(Base):
    """Every owner-contact attempt across all channels."""

    __tablename__ = "outreach_log"
    __table_args__ = (
        Index("idx_outreach_parcel", "parcel_id"),
        Index("idx_outreach_owner", "owner_id"),
        Index(
            "idx_outreach_followup",
            "follow_up_date",
            postgresql_where="follow_up_sent = FALSE AND follow_up_date IS NOT NULL",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    parcel_id: Mapped[str | None] = mapped_column(
        String(100), ForeignKey("parcels.parcel_id", ondelete="SET NULL"), index=True
    )
    owner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("owners.id", ondelete="SET NULL")
    )

    # Channel
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    # email|sms|phone_call|voicemail

    # Contact info used
    contact_value: Mapped[str] = mapped_column(Text, nullable=False)

    # Message
    template_name: Mapped[str | None] = mapped_column(String(100))
    subject: Mapped[str | None] = mapped_column(Text)
    message_body: Mapped[str | None] = mapped_column(Text)

    # Approval / status
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    # pending|approved|sent|delivered|opened|replied|bounced|failed|declined
    approved_by: Mapped[str | None] = mapped_column(String(255))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Delivery tracking
    delivery_status: Mapped[str | None] = mapped_column(String(50))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bounce_reason: Mapped[str | None] = mapped_column(Text)

    # Phone call specific
    call_duration: Mapped[int | None] = mapped_column(Integer)  # seconds
    call_outcome: Mapped[str | None] = mapped_column(String(30))
    # answered|voicemail|no_answer|busy|wrong_number|declined
    call_notes: Mapped[str | None] = mapped_column(Text)
    call_recording_url: Mapped[str | None] = mapped_column(Text)

    # Follow-up scheduling
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    follow_up_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Provider references
    provider: Mapped[str | None] = mapped_column(String(30))  # sendgrid|twilio
    provider_msg_id: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="outreach_logs", lazy="raise")  # noqa: F821
    owner: Mapped["Owner | None"] = relationship(  # noqa: F821
        "Owner", back_populates="outreach_logs", lazy="raise"
    )

    def __repr__(self) -> str:
        return (
            f"<OutreachLog id={self.id} channel={self.channel!r} status={self.status!r}>"
        )


class DoNotContact(Base):
    """Opt-out / DNC list — checked before every outreach attempt."""

    __tablename__ = "do_not_contact"
    __table_args__ = (
        UniqueConstraint("contact_value", "contact_type", name="uq_dnc_contact"),
        Index("idx_dnc_lookup", "contact_value", "contact_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contact_value: Mapped[str] = mapped_column(Text, nullable=False)
    contact_type: Mapped[str] = mapped_column(String(10), nullable=False)  # email|phone|sms
    reason: Mapped[str | None] = mapped_column(String(50))
    # opt_out|unsubscribe|dnc_registry|manual|bounced
    source: Mapped[str | None] = mapped_column(String(50))
    # twilio_stop|sendgrid_unsub|manual|dnc_check
    owner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("owners.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return f"<DoNotContact id={self.id} type={self.contact_type!r} reason={self.reason!r}>"


class OutreachTemplate(Base):
    """Reusable message templates for each channel and instrument type."""

    __tablename__ = "outreach_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)  # email|sms|phone_script
    instrument_type: Mapped[str | None] = mapped_column(String(30))
    # lien_certificate|tax_deed|null (both)
    subject: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list[str] | None] = mapped_column(ARRAY(Text))  # Jinja2 variable names
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<OutreachTemplate id={self.id} name={self.template_name!r} "
            f"channel={self.channel!r}>"
        )
