"""split procurement/restock 字段 + 安全库存 + EU 映射

Revision ID: 20260420_0900
Revises: 20260419_0000
Create Date: 2026-04-20 09:00:00

一次性完成：
1. global_config：加 safety_stock_days / eu_countries；删 calc_enabled / calc_cron /
   include_tax / default_purchase_warehouse_id。
2. suggestion：加 procurement_item_count / restock_item_count。
3. suggestion_item：加 purchase_qty / purchase_date；把 export_status 等三字段
   rename 为 restock_*；新增 procurement_export_status 等三字段 + 对应索引。
4. suggestion_snapshot：加 snapshot_type；唯一约束扩展为 (suggestion_id,
   snapshot_type, version)。
5. suggestion_snapshot_item：加 purchase_qty / purchase_date。
6. 源表加 original_* 列作 EU 映射审计：order_header.original_country_code /
   product_listing.original_marketplace_id / in_transit_record.original_target_country /
   inventory_snapshot_latest.original_country。
7. 数据迁移：把 DE/FR/IT/ES/NL/BE/PL/SE/IE 九国原地映射为 EU。
8. 归档所有 draft 建议单，清空全部 suggestion_snapshot / suggestion_snapshot_item /
   excel_export_log（快照结构变更后旧快照无法兼容）。
9. 业务人员角色补 restock:operate 权限。

项目未上线，按 AGENTS.md §11 约束，不提供 downgrade。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260420_0900"
down_revision = "20260419_0000"
branch_labels = None
depends_on = None


# EU 九国（UK=GB 不在其中）
EU_COUNTRIES: list[str] = ["DE", "FR", "IT", "ES", "NL", "BE", "PL", "SE", "IE"]


def upgrade() -> None:
    # ─── 1. global_config：新增字段 ───
    op.add_column(
        "global_config",
        sa.Column(
            "safety_stock_days",
            sa.Integer(),
            nullable=False,
            server_default="15",
        ),
    )
    op.add_column(
        "global_config",
        sa.Column(
            "eu_countries",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    # 种子：eu_countries 默认 9 国
    op.execute(
        sa.text(
            "UPDATE global_config SET eu_countries = CAST(:v AS jsonb) WHERE id = 1"
        ).bindparams(v='["DE","FR","IT","ES","NL","BE","PL","SE","IE"]')
    )

    # ─── 2. global_config：删除废弃字段 ───
    # include_tax 有 CheckConstraint，需先 drop 约束
    op.execute('ALTER TABLE global_config DROP CONSTRAINT IF EXISTS "include_tax_enum"')
    op.drop_column("global_config", "include_tax")
    op.drop_column("global_config", "default_purchase_warehouse_id")
    op.drop_column("global_config", "calc_enabled")
    op.drop_column("global_config", "calc_cron")

    # ─── 3. suggestion：新增 item_count 计数字段 ───
    op.add_column(
        "suggestion",
        sa.Column(
            "procurement_item_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "suggestion",
        sa.Column(
            "restock_item_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # ─── 4. suggestion_item：加采购字段 ───
    op.add_column(
        "suggestion_item",
        sa.Column(
            "purchase_qty",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "suggestion_item",
        sa.Column("purchase_date", sa.Date(), nullable=True),
    )

    # ─── 5. suggestion_item：export_status 三字段 rename 为 restock_* ───
    # 先删约束和索引（按 Plan A 里的命名）
    op.execute(
        'ALTER TABLE suggestion_item DROP CONSTRAINT IF EXISTS "export_status_enum"'
    )
    op.execute(
        'ALTER TABLE suggestion_item DROP CONSTRAINT IF EXISTS '
        '"ck_suggestion_item_export_status_enum"'
    )
    op.drop_index(
        "ix_suggestion_item_export_status",
        table_name="suggestion_item",
    )

    # FK 名字来自 20260418_0900: fk_suggestion_item_exported_snapshot
    op.drop_constraint(
        "fk_suggestion_item_exported_snapshot",
        "suggestion_item",
        type_="foreignkey",
    )

    op.alter_column(
        "suggestion_item",
        "export_status",
        new_column_name="restock_export_status",
    )
    op.alter_column(
        "suggestion_item",
        "exported_snapshot_id",
        new_column_name="restock_exported_snapshot_id",
    )
    op.alter_column(
        "suggestion_item",
        "exported_at",
        new_column_name="restock_exported_at",
    )

    op.create_check_constraint(
        "restock_export_status_enum",
        "suggestion_item",
        "restock_export_status IN ('pending','exported')",
    )
    op.create_index(
        "ix_suggestion_item_restock_export_status",
        "suggestion_item",
        ["suggestion_id", "restock_export_status"],
    )
    op.create_foreign_key(
        "fk_suggestion_item_restock_exported_snapshot",
        "suggestion_item",
        "suggestion_snapshot",
        ["restock_exported_snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ─── 6. suggestion_item：新增 procurement_* 三字段 ───
    op.add_column(
        "suggestion_item",
        sa.Column(
            "procurement_export_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "suggestion_item",
        sa.Column(
            "procurement_exported_snapshot_id",
            sa.BigInteger(),
            nullable=True,
        ),
    )
    op.add_column(
        "suggestion_item",
        sa.Column(
            "procurement_exported_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "procurement_export_status_enum",
        "suggestion_item",
        "procurement_export_status IN ('pending','exported')",
    )
    op.create_index(
        "ix_suggestion_item_procurement_export_status",
        "suggestion_item",
        ["suggestion_id", "procurement_export_status"],
    )
    op.create_foreign_key(
        "fk_suggestion_item_procurement_exported_snapshot",
        "suggestion_item",
        "suggestion_snapshot",
        ["procurement_exported_snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ─── 7. suggestion_snapshot：加 snapshot_type + 唯一键扩展 ───
    op.add_column(
        "suggestion_snapshot",
        sa.Column(
            "snapshot_type",
            sa.String(length=20),
            nullable=False,
            server_default="restock",
        ),
    )
    op.create_check_constraint(
        "snapshot_type_enum",
        "suggestion_snapshot",
        "snapshot_type IN ('procurement','restock')",
    )
    op.drop_constraint(
        "uq_snapshot_suggestion_version",
        "suggestion_snapshot",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_snapshot_suggestion_type_version",
        "suggestion_snapshot",
        ["suggestion_id", "snapshot_type", "version"],
    )
    op.create_index(
        "ix_snapshot_type_suggestion",
        "suggestion_snapshot",
        ["snapshot_type", "suggestion_id"],
    )

    # ─── 8. suggestion_snapshot_item：加采购字段 ───
    op.add_column(
        "suggestion_snapshot_item",
        sa.Column("purchase_qty", sa.Integer(), nullable=True),
    )
    op.add_column(
        "suggestion_snapshot_item",
        sa.Column("purchase_date", sa.Date(), nullable=True),
    )

    # ─── 9. 源表加 original_* 审计列 ───
    op.add_column(
        "order_header",
        sa.Column(
            "original_country_code",
            sa.String(length=2),
            nullable=True,
        ),
    )
    op.add_column(
        "product_listing",
        sa.Column(
            "original_marketplace_id",
            sa.String(length=10),
            nullable=True,
        ),
    )
    op.add_column(
        "in_transit_record",
        sa.Column(
            "original_target_country",
            sa.String(length=2),
            nullable=True,
        ),
    )
    op.add_column(
        "inventory_snapshot_latest",
        sa.Column(
            "original_country",
            sa.String(length=2),
            nullable=True,
        ),
    )

    # ─── 10. 数据迁移：原地映射 EU ───
    # order_header / product_listing / inventory_snapshot_latest / in_transit_record
    # 四张表的 country/marketplace_id 列存的都是 2 字符国家码（sync 层已用
    # marketplace_to_country 归一化），直接 IN (...) 匹配即可。
    eu_set = EU_COUNTRIES

    op.execute(
        sa.text(
            """
            UPDATE order_header
            SET original_country_code = country_code,
                country_code = 'EU'
            WHERE country_code = ANY(CAST(:eu AS varchar[]))
            """
        ).bindparams(eu=eu_set)
    )
    op.execute(
        sa.text(
            """
            UPDATE product_listing
            SET original_marketplace_id = marketplace_id,
                marketplace_id = 'EU'
            WHERE marketplace_id = ANY(CAST(:eu AS varchar[]))
            """
        ).bindparams(eu=eu_set)
    )
    op.execute(
        sa.text(
            """
            UPDATE in_transit_record
            SET original_target_country = target_country,
                target_country = 'EU'
            WHERE target_country = ANY(CAST(:eu AS varchar[]))
            """
        ).bindparams(eu=eu_set)
    )
    op.execute(
        sa.text(
            """
            UPDATE inventory_snapshot_latest
            SET original_country = country,
                country = 'EU'
            WHERE country = ANY(CAST(:eu AS varchar[]))
            """
        ).bindparams(eu=eu_set)
    )

    # ─── 11. 归档所有旧 draft 建议单 + 清空快照 ───
    # 旧建议单没有 purchase_qty、procurement_item_count 等新字段的语义，
    # 统一归档并打 trigger=schema_migration；快照结构也变了，一起清掉。
    op.execute(
        sa.text(
            """
            UPDATE suggestion
            SET status = 'archived',
                archived_trigger = 'schema_migration',
                archived_at = NOW()
            WHERE status = 'draft'
            """
        )
    )
    op.execute("DELETE FROM excel_export_log")
    op.execute("DELETE FROM suggestion_snapshot_item")
    op.execute("DELETE FROM suggestion_snapshot")

    # ─── 12. 权限补齐：业务人员 += restock:operate ───
    op.execute(
        sa.text(
            """
            INSERT INTO role_permission (role_id, permission_id)
            SELECT r.id, p.id
            FROM role r
            CROSS JOIN permission p
            WHERE r.name = '业务人员'
              AND p.code = 'restock:operate'
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    raise NotImplementedError(
        "AGENTS.md §11：数据库迁移不支持自动回退，请恢复备份"
    )
