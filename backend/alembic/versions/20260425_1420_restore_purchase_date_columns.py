"""compat marker for production databases at 20260425_1420.

Revision ID: 20260425_1420
Revises: 20260424_0100
Create Date: 2026-04-25 14:20:00

生产库曾部署过 master 侧兼容迁移并将 alembic_version 推进到
20260425_1420。补货日期相关真实迁移链已经包含
20260423_1100_add_restock_dates 与 20260424_0100_drop_purchase_date，
当前代码不再读取 purchase_date，因此这里仅保留 revision 拓扑，
避免生产库回到该分支时出现 "Can't locate revision"。
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "20260425_1420"
down_revision = "20260424_0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md §11")
