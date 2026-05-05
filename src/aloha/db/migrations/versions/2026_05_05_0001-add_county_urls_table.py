"""add county_urls table

Revision ID: a3f8c2d1e045
Revises: 2026_03_17_0001
Create Date: 2026-05-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "a3f8c2d1e045"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "county_urls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("state", sa.String(2), nullable=False, index=True),
        sa.Column("county", sa.String(100), nullable=False, index=True),
        sa.Column("url_type", sa.String(30), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("source", sa.String(30), nullable=False, server_default="seed"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("state", "county", "url_type", name="uq_county_url_type"),
    )


def downgrade() -> None:
    op.drop_table("county_urls")
