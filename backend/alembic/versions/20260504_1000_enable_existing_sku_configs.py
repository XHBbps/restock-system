"""enable existing sku configs.

Revision ID: 20260504_1000
Revises: 20260503_1700
Create Date: 2026-05-04 10:00:00

"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260504_1000"
down_revision = "20260503_1700"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE sku_config SET enabled = true WHERE enabled = false")


def downgrade() -> None:
    # Data migration is intentionally irreversible: do not re-disable SKUs on downgrade.
    return None
