"""add allocation_snapshot to suggestion_item

Revision ID: 20260409_0935
Revises: 20260408_1500
Create Date: 2026-04-09 09:35:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260409_0935"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "suggestion_item",
        sa.Column("allocation_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("suggestion_item", "allocation_snapshot")
