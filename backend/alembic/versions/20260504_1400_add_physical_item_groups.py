"""add physical item groups.

Revision ID: 20260504_1400
Revises: 20260504_1000
Create Date: 2026-05-04 14:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260504_1400"
down_revision = "20260504_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "physical_item_group",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("primary_sku", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_physical_item_group_name"),
    )
    op.create_index(
        "ix_physical_item_group_enabled",
        "physical_item_group",
        ["enabled"],
        unique=False,
    )
    op.create_table(
        "physical_item_sku_alias",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["group_id"], ["physical_item_group.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku", name="uq_physical_item_sku_alias_sku"),
    )
    op.create_index(
        "ix_physical_item_sku_alias_group_id",
        "physical_item_sku_alias",
        ["group_id"],
        unique=False,
    )


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md section 11")
