"""restore purchase_date columns for current master schema.

Revision ID: 20260425_1420
Revises: 20260424_0100
Create Date: 2026-04-25 14:20:00

当前应用模型和 API 仍读取：
- suggestion_item.purchase_date
- suggestion_snapshot_item.purchase_date

若生产库曾执行未进入 master 的 20260424_0100，会缺少上述字段。
本迁移以幂等方式补回字段，兼容未受影响的新环境。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260425_1420"
down_revision = "20260424_0100"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _column_exists("suggestion_item", "purchase_date"):
        op.add_column("suggestion_item", sa.Column("purchase_date", sa.Date(), nullable=True))
    if not _column_exists("suggestion_snapshot_item", "purchase_date"):
        op.add_column(
            "suggestion_snapshot_item",
            sa.Column("purchase_date", sa.Date(), nullable=True),
        )


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md §11")
