"""add restock_dates to suggestion items and snapshots

Revision ID: 20260423_1100
Revises: 20260423_1000
Create Date: 2026-04-23 11:00:00

项目未上线阶段不提供 downgrade，按 AGENTS.md §11 执行。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260423_1100"
down_revision = "20260423_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "suggestion_item",
        sa.Column(
            "restock_dates",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "suggestion_snapshot_item",
        sa.Column(
            "restock_dates",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md §11")
