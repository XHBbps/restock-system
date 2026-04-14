"""in_transit_record FK ondelete SET NULL

Revision ID: 6106e75ad360
Revises: 20260414_2400
Create Date: 2026-04-15 06:53:38.625567+08:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6106e75ad360"
down_revision: str | None = "20260414_2400"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "in_transit_record_target_warehouse_id_fkey",
        "in_transit_record",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "in_transit_record_target_warehouse_id_fkey",
        "in_transit_record",
        "warehouse",
        ["target_warehouse_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "in_transit_record_target_warehouse_id_fkey",
        "in_transit_record",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "in_transit_record_target_warehouse_id_fkey",
        "in_transit_record",
        "warehouse",
        ["target_warehouse_id"],
        ["id"],
    )
