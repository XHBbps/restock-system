"""add commodity master table

Revision ID: 20260503_1000
Revises: 20260502_0900
Create Date: 2026-05-03 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260503_1000"
down_revision: str | None = "20260502_0900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commodity_master",
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("commodity_id", sa.String(length=50), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=50), nullable=True),
        sa.Column("is_group", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("img_url", sa.Text(), nullable=True),
        sa.Column("purchase_days", sa.Integer(), nullable=True),
        sa.Column("child_skus", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("sku", name="pk_commodity_master"),
    )
    op.create_index("ix_commodity_master_state", "commodity_master", ["state"])
    op.create_index("ix_commodity_master_is_group", "commodity_master", ["is_group"])


def downgrade() -> None:
    op.drop_index("ix_commodity_master_is_group", table_name="commodity_master")
    op.drop_index("ix_commodity_master_state", table_name="commodity_master")
    op.drop_table("commodity_master")
