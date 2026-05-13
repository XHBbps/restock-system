"""add calculation inputs snapshot to suggestion items

Revision ID: 20260513_1500
Revises: 20260513_1000
Create Date: 2026-05-13 15:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260513_1500"
down_revision = "20260513_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "suggestion_item",
        sa.Column(
            "calculation_inputs_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("suggestion_item", "calculation_inputs_snapshot")
