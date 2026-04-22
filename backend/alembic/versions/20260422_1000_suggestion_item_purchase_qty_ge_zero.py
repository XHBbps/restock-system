"""suggestion_item.purchase_qty 加 CheckConstraint >= 0

Revision ID: 20260422_1000
Revises: 20260420_0900
Create Date: 2026-04-22 10:00:00

背景：engine/step4_total.py `compute_total` 在本地库存过剩时可能返回负数，
历史上可能已持久化为负。本迁移：
1. UPDATE 已存在的 purchase_qty < 0 行到 0
2. 加 CheckConstraint `purchase_qty >= 0` 防止后续回归

（engine 代码侧已同步加 `max(0, ...)` clamp，双重保护）

项目未上线阶段，按 AGENTS.md §11 约束，不提供 downgrade。
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260422_1000"
down_revision = "20260420_0900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 修复历史脏数据
    op.execute(
        "UPDATE suggestion_item SET purchase_qty = 0 WHERE purchase_qty < 0"
    )

    # 2. 加 CheckConstraint
    op.create_check_constraint(
        "purchase_qty_non_negative",
        "suggestion_item",
        "purchase_qty >= 0",
    )


def downgrade() -> None:
    # 项目未上线，不提供 downgrade
    raise NotImplementedError("downgrade not supported per AGENTS.md §11")
