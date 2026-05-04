"""add order platform purchase index.

Revision ID: 20260504_1800
Revises: 20260504_1600
Create Date: 2026-05-04 18:00:00
"""

from __future__ import annotations

from alembic import op

revision = "20260504_1800"
down_revision = "20260504_1600"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_order_header_platform_purchase",
        "order_header",
        ["order_platform", "purchase_date"],
    )


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md section 11")
