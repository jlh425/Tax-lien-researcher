"""CountyUrl model — cached assessor/tax-collector URLs per county."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from aloha.db.models.base import Base, TimestampMixin


class CountyUrl(Base, TimestampMixin):
    """Persisted county assessor/tax-collector URLs for reliable resolution."""

    __tablename__ = "county_urls"
    __table_args__ = (
        UniqueConstraint("state", "county", "url_type", name="uq_county_url_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    state: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    county: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    url_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # assessor | tax_collector | delinquent_list | gis
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="seed"
    )  # seed | searxng | llm_validated
