"""add order info match import task file table

Revision ID: 20260513_1000
Revises: 20260511_1500
Create Date: 2026-05-13 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260513_1000"
down_revision = "20260511_1500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_info_match_import_file",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.BigInteger(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_order_info_match_import_file_expires",
        "order_info_match_import_file",
        ["expires_at"],
    )
    op.create_index(
        "ix_order_info_match_import_file_task",
        "order_info_match_import_file",
        ["task_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_order_info_match_import_file_task", table_name="order_info_match_import_file")
    op.drop_index("ix_order_info_match_import_file_expires", table_name="order_info_match_import_file")
    op.drop_table("order_info_match_import_file")
