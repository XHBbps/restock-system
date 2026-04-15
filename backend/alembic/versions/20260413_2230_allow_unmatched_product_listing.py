"""allow unmatched product listing rows

Revision ID: 20260413_2230
Revises: 20260413_1830
Create Date: 2026-04-13 22:30:00
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260413_2230"
down_revision = "20260413_1830"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("product_listing", "commodity_sku", existing_type=sa.String(length=100), nullable=True)
    op.alter_column("product_listing", "commodity_id", existing_type=sa.String(length=50), nullable=True)


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported. Restore from backup before rollback.")
