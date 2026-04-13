"""extend saihu_po_number length

Revision ID: 20260413_1830
Revises: 20260411_1500
Create Date: 2026-04-13 18:30:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260413_1830"
down_revision = "20260411_1500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "suggestion_item",
        "saihu_po_number",
        existing_type=sa.String(length=50),
        type_=sa.String(length=255),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "suggestion_item",
        "saihu_po_number",
        existing_type=sa.String(length=255),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
