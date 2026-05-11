"""add calculation warnings to suggestion rows

Revision ID: 20260511_1500
Revises: 20260509_1000
Create Date: 2026-05-11 15:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260511_1500"
down_revision = "20260509_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "suggestion_item",
        sa.Column(
            "calculation_warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "suggestion_snapshot_item",
        sa.Column(
            "calculation_warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("suggestion_snapshot_item", "calculation_warnings")
    op.drop_column("suggestion_item", "calculation_warnings")
