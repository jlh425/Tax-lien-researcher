"""Document chunk model — text chunks for RAG (vectors stored in Qdrant)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aloha.db.models.base import Base


class DocumentChunk(Base):
    """A chunk of text from a source document.

    Used by the RAG layer to answer questions about a parcel or owner.
    Embedding vectors are stored externally in Qdrant, keyed by ``id``.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("idx_chunks_parcel", "parcel_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parcel_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("parcels.parcel_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    entity_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=True
    )
    source_type: Mapped[str | None] = mapped_column(String(50))
    source_url: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────
    parcel: Mapped["Parcel | None"] = relationship(  # noqa: F821
        "Parcel", back_populates="document_chunks", lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk id={self.id} parcel={self.parcel_id!r} type={self.source_type!r}>"
