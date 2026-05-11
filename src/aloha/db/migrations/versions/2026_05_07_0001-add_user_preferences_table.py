"""add user_preferences table

Revision ID: b5e9d4f2a187
Revises: a3f8c2d1e045
Create Date: 2026-05-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "b5e9d4f2a187"
down_revision = "a3f8c2d1e045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "scoring_weights",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "api_keys",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
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
        sa.UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
