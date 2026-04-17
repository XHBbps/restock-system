"""redesign suggestion model to export + snapshot

Revision ID: 20260418_0900
Revises: 20260416_1700
Create Date: 2026-04-18 09:00:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260418_0900"
down_revision = "20260416_1700"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── 1. 清空旧数据（项目未上线，dev 数据无保留价值） ───
    op.execute("DELETE FROM suggestion_item")
    op.execute("DELETE FROM suggestion")

    # ─── 2. suggestion_item：删除推送字段 + 加导出字段 ───
    op.execute('ALTER TABLE suggestion_item DROP CONSTRAINT IF EXISTS "ck_suggestion_item_ck_suggestion_item_push_status_enum"')
    op.drop_column("suggestion_item", "push_status")
    op.drop_column("suggestion_item", "push_error")
    op.drop_column("suggestion_item", "push_attempt_count")
    op.drop_column("suggestion_item", "push_blocker")
    op.drop_column("suggestion_item", "saihu_po_number")
    op.drop_column("suggestion_item", "pushed_at")
    op.drop_column("suggestion_item", "commodity_id")

    op.add_column(
        "suggestion_item",
        sa.Column(
            "export_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "suggestion_item",
        sa.Column("exported_snapshot_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "suggestion_item",
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "export_status_enum",
        "suggestion_item",
        "export_status IN ('pending','exported')",
    )
    op.create_index(
        "ix_suggestion_item_export_status",
        "suggestion_item",
        ["suggestion_id", "export_status"],
    )

    # ─── 3. suggestion：收缩 status 枚举 + 归档字段 ───
    op.execute('ALTER TABLE suggestion DROP CONSTRAINT IF EXISTS "ck_suggestion_ck_suggestion_status_enum"')
    op.create_check_constraint(
        "status_enum",
        "suggestion",
        "status IN ('draft','archived','error')",
    )
    op.add_column(
        "suggestion",
        sa.Column("archived_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "suggestion",
        sa.Column("archived_trigger", sa.String(length=20), nullable=True),
    )
    op.create_foreign_key(
        "fk_suggestion_archived_by_sys_user",
        "suggestion",
        "sys_user",
        ["archived_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # 清理已不使用的推送计数字段（保留 total_items）
    op.drop_column("suggestion", "pushed_items")
    op.drop_column("suggestion", "failed_items")

    # ─── 4. 新表 suggestion_snapshot ───
    op.create_table(
        "suggestion_snapshot",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "suggestion_id",
            sa.BigInteger(),
            sa.ForeignKey("suggestion.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("exported_by", sa.Integer(), sa.ForeignKey("sys_user.id"), nullable=True),
        sa.Column(
            "exported_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("exported_from_ip", sa.String(length=45), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column(
            "global_config_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "generation_status",
            sa.String(length=20),
            nullable=False,
            server_default="generating",
        ),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("generation_error", sa.Text(), nullable=True),
        sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "generation_status IN ('generating','ready','failed')",
            name="generation_status_enum",
        ),
        sa.UniqueConstraint("suggestion_id", "version", name="uq_snapshot_suggestion_version"),
    )
    op.create_index(
        "ix_suggestion_snapshot_suggestion",
        "suggestion_snapshot",
        ["suggestion_id"],
    )
    op.create_index(
        "ix_suggestion_snapshot_exported_at",
        "suggestion_snapshot",
        [sa.text("exported_at DESC")],
    )

    # ─── 5. 新表 suggestion_snapshot_item ───
    op.create_table(
        "suggestion_snapshot_item",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "snapshot_id",
            sa.BigInteger(),
            sa.ForeignKey("suggestion_snapshot.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("commodity_sku", sa.String(length=100), nullable=False),
        sa.Column("total_qty", sa.Integer(), nullable=False),
        sa.Column(
            "country_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "warehouse_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("urgent", sa.Boolean(), nullable=False),
        sa.Column(
            "velocity_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "sale_days_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("commodity_name", sa.String(length=500), nullable=True),
        sa.Column("main_image_url", sa.String(length=1000), nullable=True),
    )
    op.create_index(
        "ix_snapshot_item_snapshot",
        "suggestion_snapshot_item",
        ["snapshot_id"],
    )
    op.create_index(
        "ix_snapshot_item_sku",
        "suggestion_snapshot_item",
        ["commodity_sku"],
    )

    # suggestion_item.exported_snapshot_id 外键（snapshot 表建好后）
    op.create_foreign_key(
        "fk_suggestion_item_exported_snapshot",
        "suggestion_item",
        "suggestion_snapshot",
        ["exported_snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ─── 6. 新表 excel_export_log ───
    op.create_table(
        "excel_export_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "snapshot_id",
            sa.BigInteger(),
            sa.ForeignKey("suggestion_snapshot.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("performed_by", sa.Integer(), sa.ForeignKey("sys_user.id"), nullable=True),
        sa.Column(
            "performed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("performed_from_ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "action IN ('generate','download')",
            name="action_enum",
        ),
    )
    op.create_index(
        "ix_export_log_snapshot",
        "excel_export_log",
        ["snapshot_id", sa.text("performed_at DESC")],
    )

    # ─── 7. global_config：生成开关 ───
    op.add_column(
        "global_config",
        sa.Column(
            "suggestion_generation_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "global_config",
        sa.Column("generation_toggle_updated_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "global_config",
        sa.Column(
            "generation_toggle_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_global_config_toggle_user",
        "global_config",
        "sys_user",
        ["generation_toggle_updated_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
