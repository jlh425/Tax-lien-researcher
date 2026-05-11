"""UserPreferences model — per-user scoring weights and API keys."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aloha.db.models.base import Base, TimestampMixin


class UserPreferences(Base, TimestampMixin):
    """Persisted user preferences for scoring weights and external API keys."""

    __tablename__ = "user_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # JSONB blob storing scoring weight sliders (e.g. lien_to_value, etc.)
    scoring_weights: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # JSONB blob storing user-provided API keys (e.g. google_maps)
    api_keys: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # ── Relationships ─────────────────────────────────────────────────────
    user: Mapped[User] = relationship(  # noqa: F821
        "User", lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<UserPreferences id={self.id} user_id={self.user_id}>"
