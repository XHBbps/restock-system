"""compat marker for restock_dates branch.

Revision ID: 20260423_1100
Revises: 20260423_1000
Create Date: 2026-04-25 14:20:00

生产环境曾短暂部署过本地镜像，该镜像包含 20260423_1100 /
20260424_0100 两个未进入 master 的 Alembic revision。当前 master
源码不使用 restock_dates 字段，因此这里保留 revision 拓扑用于识别
已执行过的生产库版本，不对 schema 做变更。
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "20260423_1100"
down_revision = "20260423_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md §11")
