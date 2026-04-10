"""initial schema (20 tables + seed data)

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-08 15:00:00+08:00

创建所有 20 张业务表 + 种子 sync_state 行 + 种子 global_config 行。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ==================== global_config ====================
    op.create_table(
        "global_config",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("buffer_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("target_days", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("lead_time_days", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("sync_interval_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("calc_cron", sa.String(length=50), nullable=False, server_default="0 8 * * *"),
        sa.Column("default_purchase_warehouse_id", sa.String(length=50), nullable=True),
        sa.Column("include_tax", sa.String(length=1), nullable=False, server_default="0"),
        sa.Column("shop_sync_mode", sa.String(length=20), nullable=False, server_default="all"),
        sa.Column("login_password_hash", sa.String(length=255), nullable=False),
        sa.Column("login_failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("login_locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_global_config_single_row"),
        sa.CheckConstraint("include_tax IN ('0','1')", name="ck_global_config_include_tax_enum"),
        sa.CheckConstraint(
            "shop_sync_mode IN ('all','specific')", name="ck_global_config_shop_sync_mode_enum"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_global_config"),
    )

    # ==================== access_token_cache ====================
    op.create_table(
        "access_token_cache",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_access_token_cache_single_row"),
        sa.PrimaryKeyConstraint("id", name="pk_access_token_cache"),
    )

    # ==================== warehouse ====================
    op.create_table(
        "warehouse",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.Integer(), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("replenish_site_raw", sa.String(length=50), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_warehouse"),
    )
    op.create_index(
        "ix_warehouse_country",
        "warehouse",
        ["country"],
        postgresql_where=sa.text("country IS NOT NULL"),
    )
    op.create_index("ix_warehouse_type", "warehouse", ["type"])

    # ==================== shop ====================
    op.create_table(
        "shop",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("seller_id", sa.String(length=100), nullable=True),
        sa.Column("region", sa.String(length=10), nullable=True),
        sa.Column("marketplace_id", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("ad_status", sa.String(length=50), nullable=True),
        sa.Column("sync_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_shop"),
    )
    op.create_index("ix_shop_status", "shop", ["status"])

    # ==================== sku_config ====================
    op.create_table(
        "sku_config",
        sa.Column("commodity_sku", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("commodity_sku", name="pk_sku_config"),
    )
    op.create_index(
        "ix_sku_config_enabled",
        "sku_config",
        ["enabled"],
        postgresql_where=sa.text("enabled = true"),
    )

    # ==================== product_listing ====================
    op.create_table(
        "product_listing",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("commodity_sku", sa.String(length=100), nullable=False),
        sa.Column("commodity_id", sa.String(length=50), nullable=False),
        sa.Column("shop_id", sa.String(length=50), nullable=False),
        sa.Column("marketplace_id", sa.String(length=10), nullable=False),
        sa.Column("seller_sku", sa.String(length=100), nullable=True),
        sa.Column("parent_sku", sa.String(length=100), nullable=True),
        sa.Column("commodity_name", sa.Text(), nullable=True),
        sa.Column("main_image", sa.Text(), nullable=True),
        sa.Column("day7_sale_num", sa.Integer(), nullable=True),
        sa.Column("day14_sale_num", sa.Integer(), nullable=True),
        sa.Column("day30_sale_num", sa.Integer(), nullable=True),
        sa.Column("is_matched", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("online_status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_product_listing"),
        sa.UniqueConstraint(
            "shop_id", "marketplace_id", "seller_sku", name="uq_product_listing_key"
        ),
    )
    op.create_index(
        "ix_product_listing_sku_mkt", "product_listing", ["commodity_sku", "marketplace_id"]
    )
    op.create_index("ix_product_listing_commodity_sku", "product_listing", ["commodity_sku"])

    # ==================== inventory_snapshot_latest ====================
    op.create_table(
        "inventory_snapshot_latest",
        sa.Column("commodity_sku", sa.String(length=100), nullable=False),
        sa.Column("warehouse_id", sa.String(length=50), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("available", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouse.id"],
            name="fk_inventory_snapshot_latest_warehouse_id_warehouse",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "commodity_sku", "warehouse_id", name="pk_inventory_snapshot_latest"
        ),
    )
    op.create_index(
        "ix_inventory_latest_country_sku",
        "inventory_snapshot_latest",
        ["country", "commodity_sku"],
    )

    # ==================== inventory_snapshot_history ====================
    op.create_table(
        "inventory_snapshot_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("commodity_sku", sa.String(length=100), nullable=False),
        sa.Column("warehouse_id", sa.String(length=50), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("available", sa.Integer(), nullable=False),
        sa.Column("reserved", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_inventory_snapshot_history"),
    )
    op.create_index(
        "ix_inventory_history_date_sku",
        "inventory_snapshot_history",
        ["snapshot_date", "commodity_sku"],
    )
    op.create_index(
        "ix_inventory_history_sku_date",
        "inventory_snapshot_history",
        ["commodity_sku", "snapshot_date"],
    )

    # ==================== in_transit_record ====================
    op.create_table(
        "in_transit_record",
        sa.Column("saihu_out_record_id", sa.String(length=50), nullable=False),
        sa.Column("out_warehouse_no", sa.String(length=50), nullable=True),
        sa.Column("target_warehouse_id", sa.String(length=50), nullable=True),
        sa.Column("target_country", sa.String(length=2), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=True),
        sa.Column("is_in_transit", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["target_warehouse_id"],
            ["warehouse.id"],
            name="fk_in_transit_record_target_warehouse_id_warehouse",
        ),
        sa.PrimaryKeyConstraint("saihu_out_record_id", name="pk_in_transit_record"),
    )
    op.create_index(
        "ix_in_transit_record_active",
        "in_transit_record",
        ["is_in_transit", "target_country"],
        postgresql_where=sa.text("is_in_transit = true"),
    )
    op.create_index(
        "ix_in_transit_record_last_seen", "in_transit_record", ["last_seen_at"]
    )

    # ==================== in_transit_item ====================
    op.create_table(
        "in_transit_item",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("saihu_out_record_id", sa.String(length=50), nullable=False),
        sa.Column("commodity_sku", sa.String(length=100), nullable=False),
        sa.Column("goods", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["saihu_out_record_id"],
            ["in_transit_record.saihu_out_record_id"],
            name="fk_in_transit_item_saihu_out_record_id_in_transit_record",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_in_transit_item"),
    )
    op.create_index("ix_in_transit_item_record", "in_transit_item", ["saihu_out_record_id"])
    op.create_index("ix_in_transit_item_sku", "in_transit_item", ["commodity_sku"])

    # ==================== order_header ====================
    op.create_table(
        "order_header",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("shop_id", sa.String(length=50), nullable=False),
        sa.Column("amazon_order_id", sa.String(length=50), nullable=False),
        sa.Column("marketplace_id", sa.String(length=10), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("order_status", sa.String(length=30), nullable=False),
        sa.Column("order_total_currency", sa.String(length=10), nullable=True),
        sa.Column("order_total_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("fulfillment_channel", sa.String(length=10), nullable=True),
        sa.Column("purchase_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_update_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_buyer_requested_cancel", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("refund_status", sa.String(length=10), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_order_header"),
        sa.UniqueConstraint("shop_id", "amazon_order_id", name="uq_order_header_key"),
    )
    op.create_index("ix_order_header_purchase_date", "order_header", ["purchase_date"])
    op.create_index(
        "ix_order_header_country_purchase", "order_header", ["country_code", "purchase_date"]
    )
    op.create_index("ix_order_header_last_update", "order_header", ["last_update_date"])

    # ==================== order_item ====================
    op.create_table(
        "order_item",
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("order_item_id", sa.String(length=50), nullable=False),
        sa.Column("commodity_sku", sa.String(length=100), nullable=False),
        sa.Column("seller_sku", sa.String(length=100), nullable=True),
        sa.Column("quantity_ordered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity_shipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity_unfulfillable", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("refund_num", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("item_price_currency", sa.String(length=10), nullable=True),
        sa.Column("item_price_amount", sa.Numeric(18, 4), nullable=True),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["order_header.id"],
            name="fk_order_item_order_id_order_header",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("order_id", "order_item_id", name="pk_order_item"),
    )
    op.create_index("ix_order_item_commodity_sku", "order_item", ["commodity_sku"])

    # ==================== order_detail ====================
    op.create_table(
        "order_detail",
        sa.Column("shop_id", sa.String(length=50), nullable=False),
        sa.Column("amazon_order_id", sa.String(length=50), nullable=False),
        sa.Column("postal_code", sa.String(length=50), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("state_or_region", sa.String(length=100), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("detail_address", sa.Text(), nullable=True),
        sa.Column("receiver_name", sa.String(length=255), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("shop_id", "amazon_order_id", name="pk_order_detail"),
    )
    op.create_index(
        "ix_order_detail_country_postal",
        "order_detail",
        ["country_code", "postal_code"],
        postgresql_where=sa.text("postal_code IS NOT NULL"),
    )

    # ==================== order_detail_fetch_log ====================
    op.create_table(
        "order_detail_fetch_log",
        sa.Column("shop_id", sa.String(length=50), nullable=False),
        sa.Column("amazon_order_id", sa.String(length=50), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("saihu_code", sa.Integer(), nullable=True),
        sa.Column("saihu_msg", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint(
            "shop_id", "amazon_order_id", name="pk_order_detail_fetch_log"
        ),
    )

    # ==================== zipcode_rule ====================
    op.create_table(
        "zipcode_rule",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("prefix_length", sa.Integer(), nullable=False),
        sa.Column("value_type", sa.String(length=10), nullable=False),
        sa.Column("operator", sa.String(length=5), nullable=False),
        sa.Column("compare_value", sa.String(length=50), nullable=False),
        sa.Column("warehouse_id", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouse.id"],
            name="fk_zipcode_rule_warehouse_id_warehouse",
        ),
        sa.CheckConstraint(
            "value_type IN ('number','string')", name="ck_zipcode_rule_value_type_enum"
        ),
        sa.CheckConstraint(
            "operator IN ('=','!=','>','>=','<','<=')",
            name="ck_zipcode_rule_operator_enum",
        ),
        sa.CheckConstraint(
            "prefix_length BETWEEN 1 AND 10", name="ck_zipcode_rule_prefix_length_range"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_zipcode_rule"),
    )
    op.create_index(
        "ix_zipcode_rule_country_priority", "zipcode_rule", ["country", "priority"]
    )

    # ==================== suggestion ====================
    op.create_table(
        "suggestion",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("global_config_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pushed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("triggered_by", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft','partial','pushed','archived','error')",
            name="ck_suggestion_status_enum",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_suggestion"),
    )
    op.create_index("ix_suggestion_created_at", "suggestion", ["created_at"])
    op.create_index("ix_suggestion_status", "suggestion", ["status"])

    # ==================== suggestion_item ====================
    op.create_table(
        "suggestion_item",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("suggestion_id", sa.BigInteger(), nullable=False),
        sa.Column("commodity_sku", sa.String(length=100), nullable=False),
        sa.Column("commodity_id", sa.String(length=50), nullable=True),
        sa.Column("total_qty", sa.Integer(), nullable=False),
        sa.Column("country_breakdown", postgresql.JSONB(), nullable=False),
        sa.Column("warehouse_breakdown", postgresql.JSONB(), nullable=False),
        sa.Column("t_purchase", postgresql.JSONB(), nullable=False),
        sa.Column("t_ship", postgresql.JSONB(), nullable=False),
        sa.Column("velocity_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("sale_days_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("urgent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("push_blocker", sa.String(length=50), nullable=True),
        sa.Column("push_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("saihu_po_number", sa.String(length=50), nullable=True),
        sa.Column("push_error", sa.Text(), nullable=True),
        sa.Column("push_attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["suggestion_id"],
            ["suggestion.id"],
            name="fk_suggestion_item_suggestion_id_suggestion",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "push_status IN ('pending','pushed','push_failed','blocked')",
            name="ck_suggestion_item_push_status_enum",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_suggestion_item"),
    )
    op.create_index("ix_suggestion_item_suggestion", "suggestion_item", ["suggestion_id"])
    op.create_index("ix_suggestion_item_sku", "suggestion_item", ["commodity_sku"])
    op.create_index(
        "ix_suggestion_item_urgent",
        "suggestion_item",
        ["urgent"],
        postgresql_where=sa.text("urgent = true"),
    )

    # ==================== task_run ====================
    op.create_table(
        "task_run",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_name", sa.String(length=50), nullable=False),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("trigger_source", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column(
            "payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("current_step", sa.String(length=100), nullable=True),
        sa.Column("step_detail", sa.Text(), nullable=True),
        sa.Column("total_steps", sa.Integer(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("result_payload", postgresql.JSONB(), nullable=True),
        sa.Column("worker_id", sa.String(length=100), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','running','success','failed','skipped','cancelled')",
            name="ck_task_run_status_enum",
        ),
        sa.CheckConstraint(
            "trigger_source IN ('scheduler','manual')",
            name="ck_task_run_trigger_source_enum",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_task_run"),
    )
    # * 核心部分唯一索引
    op.create_index(
        "uq_task_run_active_dedupe",
        "task_run",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )
    op.create_index(
        "ix_task_run_pending_priority",
        "task_run",
        ["status", "priority", "created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index("ix_task_run_job_created", "task_run", ["job_name", "created_at"])
    op.create_index(
        "ix_task_run_lease",
        "task_run",
        ["lease_expires_at"],
        postgresql_where=sa.text("status = 'running'"),
    )

    # ==================== sync_state ====================
    op.create_table(
        "sync_state",
        sa.Column("job_name", sa.String(length=50), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=20), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("job_name", name="pk_sync_state"),
    )

    # ==================== api_call_log ====================
    op.create_table(
        "api_call_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("endpoint", sa.String(length=200), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("called_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("saihu_code", sa.Integer(), nullable=True),
        sa.Column("saihu_msg", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("error_type", sa.String(length=50), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id", name="pk_api_call_log"),
    )
    op.create_index("ix_api_call_log_endpoint_time", "api_call_log", ["endpoint", "called_at"])
    op.create_index(
        "ix_api_call_log_failed",
        "api_call_log",
        ["called_at"],
        postgresql_where=sa.text("saihu_code IS NOT NULL AND saihu_code != 0"),
    )

    # ==================== 种子数据 ====================
    # sync_state 预插入所有 job 行
    job_names = [
        "sync_product_listing",
        "sync_warehouse",
        "sync_inventory",
        "sync_out_records",
        "sync_order_list",
        "sync_order_detail",
        "sync_shop",
        "daily_archive",
        "calc_engine",
    ]
    for job_name in job_names:
        op.execute(
            sa.text("INSERT INTO sync_state (job_name) VALUES (:j)").bindparams(j=job_name)
        )


def downgrade() -> None:
    # 反向删除(按依赖顺序)
    op.drop_index("ix_api_call_log_failed", table_name="api_call_log")
    op.drop_index("ix_api_call_log_endpoint_time", table_name="api_call_log")
    op.drop_table("api_call_log")

    op.drop_table("sync_state")

    op.drop_index("ix_task_run_lease", table_name="task_run")
    op.drop_index("ix_task_run_job_created", table_name="task_run")
    op.drop_index("ix_task_run_pending_priority", table_name="task_run")
    op.drop_index("uq_task_run_active_dedupe", table_name="task_run")
    op.drop_table("task_run")

    op.drop_index("ix_suggestion_item_urgent", table_name="suggestion_item")
    op.drop_index("ix_suggestion_item_sku", table_name="suggestion_item")
    op.drop_index("ix_suggestion_item_suggestion", table_name="suggestion_item")
    op.drop_table("suggestion_item")

    op.drop_index("ix_suggestion_status", table_name="suggestion")
    op.drop_index("ix_suggestion_created_at", table_name="suggestion")
    op.drop_table("suggestion")

    op.drop_index("ix_zipcode_rule_country_priority", table_name="zipcode_rule")
    op.drop_table("zipcode_rule")

    op.drop_table("order_detail_fetch_log")

    op.drop_index("ix_order_detail_country_postal", table_name="order_detail")
    op.drop_table("order_detail")

    op.drop_index("ix_order_item_commodity_sku", table_name="order_item")
    op.drop_table("order_item")

    op.drop_index("ix_order_header_last_update", table_name="order_header")
    op.drop_index("ix_order_header_country_purchase", table_name="order_header")
    op.drop_index("ix_order_header_purchase_date", table_name="order_header")
    op.drop_table("order_header")

    op.drop_index("ix_in_transit_item_sku", table_name="in_transit_item")
    op.drop_index("ix_in_transit_item_record", table_name="in_transit_item")
    op.drop_table("in_transit_item")

    op.drop_index("ix_in_transit_record_last_seen", table_name="in_transit_record")
    op.drop_index("ix_in_transit_record_active", table_name="in_transit_record")
    op.drop_table("in_transit_record")

    op.drop_index("ix_inventory_history_sku_date", table_name="inventory_snapshot_history")
    op.drop_index("ix_inventory_history_date_sku", table_name="inventory_snapshot_history")
    op.drop_table("inventory_snapshot_history")

    op.drop_index("ix_inventory_latest_country_sku", table_name="inventory_snapshot_latest")
    op.drop_table("inventory_snapshot_latest")

    op.drop_index("ix_product_listing_commodity_sku", table_name="product_listing")
    op.drop_index("ix_product_listing_sku_mkt", table_name="product_listing")
    op.drop_table("product_listing")

    op.drop_index("ix_sku_config_enabled", table_name="sku_config")
    op.drop_table("sku_config")

    op.drop_index("ix_shop_status", table_name="shop")
    op.drop_table("shop")

    op.drop_index("ix_warehouse_type", table_name="warehouse")
    op.drop_index("ix_warehouse_country", table_name="warehouse")
    op.drop_table("warehouse")

    op.drop_table("access_token_cache")
    op.drop_table("global_config")
