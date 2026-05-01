"""Crawl log — audit trail and change detection for every source fetch."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aloha.db.models.base import Base


class CrawlLog(Base):
    """One row per HTTP request made by any scraper or agent.

    Used for:
    - Change detection (``content_hash`` diff)
    - Debugging failed crawls
    - Rate-limit audit trail
    """

    __tablename__ = "crawl_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parcel_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("parcels.parcel_id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    source_type: Mapped[str | None] = mapped_column(String(50))
    # tax_collector|assessor|recorder|sos|gis|court|social|auction
    source_url: Mapped[str | None] = mapped_column(Text)
    http_status: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    changed: Mapped[bool | None] = mapped_column(Boolean)
    error_message: Mapped[str | None] = mapped_column(Text)
    crawled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<CrawlLog id={self.id} source={self.source_type!r} "
            f"status={self.http_status} changed={self.changed}>"
        )
