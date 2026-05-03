"""add sku mapping rules.

Revision ID: 20260427_1800
Revises: 20260427_1200
Create Date: 2026-04-27 18:00:00

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260427_1800"
down_revision = "20260427_1200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sku_mapping_rule",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("commodity_sku", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sku_mapping_rule")),
        sa.UniqueConstraint("commodity_sku", name="uq_sku_mapping_rule_commodity_sku"),
    )
    op.create_index(
        "ix_sku_mapping_rule_enabled",
        "sku_mapping_rule",
        ["enabled"],
        unique=False,
    )
    op.create_table(
        "sku_mapping_component",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("inventory_sku", sa.String(length=100), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["sku_mapping_rule.id"],
            name=op.f("fk_sku_mapping_component_rule_id_sku_mapping_rule"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sku_mapping_component")),
        sa.UniqueConstraint("inventory_sku", name="uq_sku_mapping_component_inventory_sku"),
        sa.CheckConstraint("quantity > 0", name="ck_sku_mapping_component_quantity_positive"),
    )
    op.create_index(
        "ix_sku_mapping_component_rule_id",
        "sku_mapping_component",
        ["rule_id"],
        unique=False,
    )


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md §11")
