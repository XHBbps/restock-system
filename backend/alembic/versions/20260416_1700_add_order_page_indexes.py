"""add order page query indexes

Revision ID: 20260416_1700
Revises: 20260415_0653
Create Date: 2026-04-16 17:00:00
"""

from alembic import op

revision = "20260416_1700"
down_revision = "6106e75ad360"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_order_header_shop_purchase", "order_header", ["shop_id", "purchase_date"])
    op.create_index(
        "ix_order_header_status_purchase", "order_header", ["order_status", "purchase_date"]
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
