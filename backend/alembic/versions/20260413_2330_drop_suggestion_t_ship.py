"""Drop suggestion_item.t_ship.

Revision ID: 20260413_2330
Revises: 20260413_2230
Create Date: 2026-04-13 23:30:00
"""

from alembic import op


revision = "20260413_2330"
down_revision = "20260413_2230"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("suggestion_item", "t_ship")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported. Restore from backup before rollback.")
