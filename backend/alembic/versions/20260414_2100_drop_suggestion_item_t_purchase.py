"""drop suggestion item purchase date

Revision ID: 20260414_2100
Revises: 20260414_1500
Create Date: 2026-04-14 21:00:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260414_2100"
down_revision = "20260414_1500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("suggestion_item", "t_purchase")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
