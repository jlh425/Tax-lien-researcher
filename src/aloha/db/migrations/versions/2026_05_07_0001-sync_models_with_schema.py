"""Sync models with schema — pgvector cleanup and missing indexes.

The Qdrant migration (26955a4) removed the pgvector ``embedding`` column
from the ``DocumentChunk`` model and the ``vector`` extension, but did so
by patching the initial migration in-place rather than creating a forward
migration.  Databases created from the *original* initial migration still
carry the now-orphaned ``embedding`` column, HNSW index, and extension.

This migration also adds individual indexes on ``parcels.county`` and
``parcels.state`` to match the model's ``index=True`` declarations.  The
initial migration only created a composite ``ix_parcels_county_state``
index, which cannot serve queries that filter on ``state`` alone.

Revision ID: c7a1b3d9f021
Revises: a3f8c2d1e045
Create Date: 2026-05-07
"""

from alembic import op

# revision identifiers
revision = "c7a1b3d9f021"
down_revision = "b5e9d4f2a187"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── pgvector cleanup ─────────────────────────────────────────────
    # Drop HNSW index if it exists (created by original initial migration)
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")
    # Drop the embedding column if it exists
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
    # Drop the pgvector extension if it exists
    op.execute("DROP EXTENSION IF EXISTS vector")

    # ── Missing individual indexes on parcels ────────────────────────
    # The model declares index=True on both county and state individually,
    # but the initial migration only created a composite index.  A composite
    # (county, state) index serves county-only queries efficiently, so we
    # only need to add the missing state index for state-only filters.
    op.create_index("ix_parcels_state", "parcels", ["state"])


def downgrade() -> None:
    # ── Remove the state index ─────────────────────────────────────────────
    op.drop_index("ix_parcels_state", table_name="parcels")

    # ── Restore pgvector objects ───────────────────────────────────────────
    # Re-create the extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Re-add the embedding column
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)")
    # Re-create the HNSW index
    op.execute(
        "CREATE INDEX idx_chunks_embedding ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )
