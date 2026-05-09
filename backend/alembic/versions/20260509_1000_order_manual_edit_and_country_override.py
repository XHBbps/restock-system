"""add order manual edit lock and country name overrides.

Revision ID: 20260509_1000
Revises: 20260504_2000
Create Date: 2026-05-09 10:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260509_1000"
down_revision = "20260504_2000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO permission (code, name, group_name, sort_order, active)
            VALUES ('data_biz:edit', '业务数据-编辑', '业务数据', 0, true)
            ON CONFLICT (code) DO UPDATE
            SET name = EXCLUDED.name,
                group_name = EXCLUDED.group_name,
                active = true
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO role_permission (role_id, permission_id)
            SELECT r.id, p.id
            FROM role r
            CROSS JOIN permission p
            WHERE r.name = '业务人员'
              AND p.code = 'data_biz:edit'
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        )
    )
    op.add_column(
        "order_header",
        sa.Column("manual_edit_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "order_header",
        sa.Column("manual_edited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("order_header", sa.Column("manual_edited_by", sa.Integer(), nullable=True))
    op.add_column(
        "order_header",
        sa.Column("manual_edit_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_table(
        "country_name_override",
        sa.Column("code", sa.String(length=2), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md section 11")
