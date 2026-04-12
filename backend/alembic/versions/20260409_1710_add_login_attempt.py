"""add login_attempt table

Revision ID: 20260409_1710
Revises: 20260409_1700
Create Date: 2026-04-09 17:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260409_1710"
down_revision: str | Sequence[str] | None = "20260409_1700"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_attempt",
        sa.Column("source_key", sa.String(length=100), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("source_key", name="pk_login_attempt"),
    )


def downgrade() -> None:
    op.drop_table("login_attempt")
