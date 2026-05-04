"""add independent order sync interval.

Revision ID: 20260504_2000
Revises: 20260504_1800
Create Date: 2026-05-04 20:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260504_2000"
down_revision = "20260504_1800"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "global_config",
        sa.Column(
            "order_sync_interval_minutes",
            sa.Integer(),
            nullable=False,
            server_default="120",
        ),
    )
    op.execute("UPDATE global_config SET order_sync_interval_minutes = 120 WHERE id = 1")


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md section 11")
