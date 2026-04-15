"""in_transit_record FK ondelete SET NULL

Revision ID: 6106e75ad360
Revises: 20260414_2400
Create Date: 2026-04-15 06:53:38.625567+08:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "6106e75ad360"
down_revision: str | None = "20260414_2400"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_target_warehouse_fk_if_exists() -> None:
    op.execute(
        "ALTER TABLE in_transit_record "
        "DROP CONSTRAINT IF EXISTS in_transit_record_target_warehouse_id_fkey"
    )
    op.execute(
        "ALTER TABLE in_transit_record "
        "DROP CONSTRAINT IF EXISTS fk_in_transit_record_target_warehouse_id_warehouse"
    )


def upgrade() -> None:
    _drop_target_warehouse_fk_if_exists()
    op.create_foreign_key(
        "fk_in_transit_record_target_warehouse_id_warehouse",
        "in_transit_record",
        "warehouse",
        ["target_warehouse_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    _drop_target_warehouse_fk_if_exists()
    op.create_foreign_key(
        "fk_in_transit_record_target_warehouse_id_warehouse",
        "in_transit_record",
        "warehouse",
        ["target_warehouse_id"],
        ["id"],
    )
