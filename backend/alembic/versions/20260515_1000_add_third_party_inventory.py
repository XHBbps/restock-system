"""add third party warehouse inventory

Revision ID: 20260515_1000
Revises: 20260513_1500
Create Date: 2026-05-15 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260515_1000"
down_revision = "20260513_1500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "third_party_warehouse",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_third_party_warehouse_name"),
    )
    op.create_index(
        "ix_third_party_warehouse_country",
        "third_party_warehouse",
        ["country"],
        unique=False,
        postgresql_where=sa.text("country IS NOT NULL"),
    )

    op.create_table(
        "third_party_inventory_import_batch",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("valid_row_count", sa.Integer(), nullable=False),
        sa.Column("skipped_row_count", sa.Integer(), nullable=False),
        sa.Column("new_warehouse_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("confirmed_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status in ('pending', 'applied', 'failed', 'expired')",
            name="ck_third_party_inventory_batch_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_third_party_inventory_batch_status",
        "third_party_inventory_import_batch",
        ["status"],
        unique=False,
    )

    op.create_table(
        "third_party_inventory_import_item",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("warehouse_name_raw", sa.String(length=255), nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), nullable=True),
        sa.Column("commodity_sku", sa.String(length=100), nullable=True),
        sa.Column("available", sa.Integer(), nullable=True),
        sa.Column("reserved", sa.Integer(), nullable=True),
        sa.Column("source_row_no", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["third_party_inventory_import_batch.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["third_party_warehouse.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_third_party_inventory_item_batch",
        "third_party_inventory_import_item",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        "ix_third_party_inventory_item_warehouse",
        "third_party_inventory_import_item",
        ["warehouse_id"],
        unique=False,
    )

    op.create_table(
        "third_party_inventory_current",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("warehouse_id", sa.BigInteger(), nullable=False),
        sa.Column("commodity_sku", sa.String(length=100), nullable=False),
        sa.Column("available", sa.Integer(), nullable=False),
        sa.Column("reserved", sa.Integer(), nullable=False),
        sa.Column("source_batch_id", sa.BigInteger(), nullable=True),
        sa.Column("last_operation", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("available >= 0", name="ck_third_party_inventory_current_available"),
        sa.CheckConstraint("reserved >= 0", name="ck_third_party_inventory_current_reserved"),
        sa.ForeignKeyConstraint(
            ["source_batch_id"],
            ["third_party_inventory_import_batch.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["third_party_warehouse.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "warehouse_id",
            "commodity_sku",
            name="uq_third_party_inventory_current_wh_sku",
        ),
    )
    op.create_index(
        "ix_third_party_inventory_current_sku",
        "third_party_inventory_current",
        ["commodity_sku"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_third_party_inventory_current_sku", table_name="third_party_inventory_current")
    op.drop_table("third_party_inventory_current")
    op.drop_index("ix_third_party_inventory_item_warehouse", table_name="third_party_inventory_import_item")
    op.drop_index("ix_third_party_inventory_item_batch", table_name="third_party_inventory_import_item")
    op.drop_table("third_party_inventory_import_item")
    op.drop_index("ix_third_party_inventory_batch_status", table_name="third_party_inventory_import_batch")
    op.drop_table("third_party_inventory_import_batch")
    op.drop_index("ix_third_party_warehouse_country", table_name="third_party_warehouse")
    op.drop_table("third_party_warehouse")
