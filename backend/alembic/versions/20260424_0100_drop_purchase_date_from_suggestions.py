"""drop purchase_date from suggestion items and snapshots

Revision ID: 20260424_0100
Revises: 20260423_1100
Create Date: 2026-04-24 01:00:00

项目未上线阶段不提供 downgrade，按 AGENTS.md 第 11 节执行。
"""

from __future__ import annotations

from alembic import op

revision = "20260424_0100"
down_revision = "20260423_1100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("suggestion_snapshot_item", "purchase_date")
    op.drop_column("suggestion_item", "purchase_date")


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md 第11节")
