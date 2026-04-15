"""Extend synced out-record fields.

Revision ID: 20260414_1300
Revises: 20260413_2330
Create Date: 2026-04-14 13:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260414_1300"
down_revision = "20260413_2330"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("in_transit_record", sa.Column("warehouse_id", sa.String(length=50), nullable=True))
    op.add_column("in_transit_record", sa.Column("update_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column("in_transit_record", sa.Column("type", sa.Integer(), nullable=True))
    op.add_column("in_transit_record", sa.Column("type_name", sa.String(length=100), nullable=True))

    op.add_column("in_transit_item", sa.Column("commodity_id", sa.String(length=50), nullable=True))
    op.add_column("in_transit_item", sa.Column("per_purchase", sa.Numeric(18, 4), nullable=True))


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported. Restore from backup before rollback.")
