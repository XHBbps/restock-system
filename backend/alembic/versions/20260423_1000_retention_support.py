"""excel_export_log.file_purged_at + dashboard_snapshot.stale

Revision ID: 20260423_1000
Revises: 20260422_1000
Create Date: 2026-04-23 10:00:00

支持打包 #4 retention 三连 + Dashboard 自动失效：

1. `excel_export_log.file_purged_at DateTime(timezone=True) NULL`
   - retention_purge_job 删除磁盘 Excel 时把对应 log 的 file_purged_at 写 now。
   - download API 可依据该字段返回 410 Gone（"该版本已清理"）。

2. `dashboard_snapshot.stale BOOLEAN DEFAULT FALSE NOT NULL`
   - api/config.patch_global 改动 restock_regions / eu_countries / target_days /
     lead_time_days / buffer_days / safety_stock_days 时置为 TRUE。
   - GET /api/metrics/dashboard 检测到 stale=TRUE 时 enqueue
     refresh_dashboard_snapshot 任务并返回 snapshot_status="refreshing"。
   - 刷新完成由 dashboard_snapshot_job `_mark_ready` 同时把 stale 置回 FALSE。

项目未上线阶段，按 AGENTS.md §11 约束，不提供 downgrade。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260423_1000"
down_revision = "20260422_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "excel_export_log",
        sa.Column(
            "file_purged_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "dashboard_snapshot",
        sa.Column(
            "stale",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md §11")
