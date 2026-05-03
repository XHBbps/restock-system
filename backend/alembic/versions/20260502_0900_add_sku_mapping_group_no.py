"""add group number to sku mapping components.

Revision ID: 20260502_0900
Revises: 20260428_1000
Create Date: 2026-05-02 09:00:00

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260502_0900"
down_revision = "20260428_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sku_mapping_component",
        sa.Column("group_no", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_check_constraint(
        "ck_sku_mapping_component_group_no_positive",
        "sku_mapping_component",
        "group_no > 0",
    )
    op.create_index(
        "ix_sku_mapping_component_rule_group",
        "sku_mapping_component",
        ["rule_id", "group_no"],
        unique=False,
    )


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md section 11")
