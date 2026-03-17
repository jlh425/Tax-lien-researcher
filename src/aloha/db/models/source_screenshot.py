"""Source screenshot model — evidence capture for every data point."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ARRAY, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aloha.db.models.base import Base


class SourceScreenshot(Base):
    """Full-page Playwright screenshot taken at data-extraction time.

    The ``crop_*`` fields define the bounding box shown in the UI to highlight
    the relevant data region; clicking/mouseover shows the full page.
    """

    __tablename__ = "source_screenshots"
    __table_args__ = (
        Index("idx_screenshots_parcel", "parcel_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parcel_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("parcels.parcel_id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # tax_collector|assessor|recorder|sos|court|gis|zillow|auction
    source_name: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)

    # Crop hint for UI (bounding box of the relevant data region)
    crop_x: Mapped[int | None] = mapped_column(Integer)
    crop_y: Mapped[int | None] = mapped_column(Integer)
    crop_w: Mapped[int | None] = mapped_column(Integer)
    crop_h: Mapped[int | None] = mapped_column(Integer)

    # Fields extracted from this screenshot
    data_extracted: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    captured_at: Mapped[datetime] = mapped_column(nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────
    parcel: Mapped["Parcel"] = relationship(  # noqa: F821
        "Parcel", back_populates="source_screenshots", lazy="raise"
    )

    def __repr__(self) -> str:
        return (
            f"<SourceScreenshot id={self.id} parcel={self.parcel_id!r} "
            f"type={self.source_type!r}>"
        )
