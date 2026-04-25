"""compat marker for dropped purchase_date branch.

Revision ID: 20260424_0100
Revises: 20260423_1100
Create Date: 2026-04-25 14:21:00

生产环境的 alembic_version 可能已经停在该 revision。当前 master 源码
仍需要 suggestion_item.purchase_date 与 suggestion_snapshot_item.purchase_date，
因此本兼容 revision 只补齐 Alembic 拓扑，不在新环境中删除字段。
后续 20260425_1420 会对已受影响的生产库补回缺失字段。
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "20260424_0100"
down_revision = "20260423_1100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md §11")
