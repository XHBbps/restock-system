"""drop physical item primary sku.

Revision ID: 20260504_1600
Revises: 20260504_1400
Create Date: 2026-05-04 16:00:00
"""

from __future__ import annotations

from alembic import op

revision = "20260504_1600"
down_revision = "20260504_1400"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("physical_item_group", "primary_sku")


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md section 11")
