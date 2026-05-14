"""Property image model — GIS map, street view, satellite, listing photos."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aloha.db.models.base import Base


class PropertyImage(Base):
    """A captured image associated with a parcel.

    Priority order: gis_parcel_map → street_view → satellite → zillow_listing
    """

    __tablename__ = "property_images"
    __table_args__ = (UniqueConstraint("parcel_id", "image_type", name="uq_parcel_image_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parcel_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("parcels.parcel_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # gis_parcel_map|street_view|satellite|zillow_listing
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # GIS map overlays active when captured
    overlays: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    # ── Relationships ─────────────────────────────────────────────────────
    parcel: Mapped[Parcel] = relationship(  # noqa: F821
        "Parcel", back_populates="property_images", lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<PropertyImage id={self.id} parcel={self.parcel_id!r} type={self.image_type!r}>"
