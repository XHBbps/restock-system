"""Add unique constraint to inventory_snapshot_history and remove dead global_config columns.

Revision ID: 20260410_0001
Revises: 20260409_1710
Create Date: 2026-04-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260410_0001"
down_revision: str | Sequence[str] | None = "20260409_1710"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Remove duplicate daily archive rows before adding unique constraint
    op.execute(
        """
        DELETE FROM inventory_snapshot_history a
        USING inventory_snapshot_history b
        WHERE a.id > b.id
          AND a.commodity_sku = b.commodity_sku
          AND a.warehouse_id = b.warehouse_id
          AND a.snapshot_date = b.snapshot_date
        """
    )

    op.create_unique_constraint(
        "uq_snapshot_history_sku_wh_date",
        "inventory_snapshot_history",
        ["commodity_sku", "warehouse_id", "snapshot_date"],
    )

    op.drop_column("global_config", "login_failed_count")
    op.drop_column("global_config", "login_locked_until")


def downgrade() -> None:
    op.add_column(
        "global_config",
        sa.Column("login_locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "global_config",
        sa.Column(
            "login_failed_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.drop_constraint("uq_snapshot_history_sku_wh_date", "inventory_snapshot_history")
