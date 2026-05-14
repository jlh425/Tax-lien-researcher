"""User and subscription model."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aloha.db.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """Platform user with subscription tier and outreach identity."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    hashed_password: Mapped[str | None] = mapped_column(String(255))

    # OAuth
    auth_provider: Mapped[str | None] = mapped_column(String(50))  # google|github|email
    auth_provider_id: Mapped[str | None] = mapped_column(String(255))

    # Subscription
    tier: Mapped[str] = mapped_column(String(50), nullable=False, default="free")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255))
    subscription_status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")

    # Outreach identity
    outreach_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="individual")
    outreach_email: Mapped[str | None] = mapped_column(String(255))
    outreach_domain: Mapped[str | None] = mapped_column(String(255))
    sendgrid_api_key: Mapped[str | None] = mapped_column(Text)  # encrypted
    twilio_account_sid: Mapped[str | None] = mapped_column(String(255))  # encrypted
    twilio_auth_token: Mapped[str | None] = mapped_column(Text)  # encrypted
    twilio_phone_number: Mapped[str | None] = mapped_column(String(50))
    physical_address: Mapped[str | None] = mapped_column(Text)  # CAN-SPAM required

    # Flexible per-user settings blob
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Relationships ─────────────────────────────────────────────────────
    parcels: Mapped[list[Parcel]] = relationship(  # noqa: F821
        "Parcel", back_populates="user", lazy="raise"
    )
    outreach_logs: Mapped[list[OutreachLog]] = relationship(  # noqa: F821
        "OutreachLog", back_populates="user", lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} tier={self.tier!r}>"
