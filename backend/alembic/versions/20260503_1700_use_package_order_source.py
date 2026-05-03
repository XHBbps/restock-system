"""use package order source.

Revision ID: 20260503_1700
Revises: 20260503_1500
Create Date: 2026-05-03 17:00:00

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260503_1700"
down_revision = "20260503_1500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_header",
        sa.Column("package_sn", sa.String(length=80), server_default="", nullable=False),
    )
    op.add_column(
        "order_header",
        sa.Column("package_status", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "order_header",
        sa.Column("shop_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "order_header",
        sa.Column("postal_code", sa.String(length=50), nullable=True),
    )

    op.drop_constraint("uq_order_header_key", "order_header", type_="unique")
    op.create_unique_constraint(
        "uq_order_header_key",
        "order_header",
        ["shop_id", "amazon_order_id", "source", "package_sn"],
    )
    op.create_index(
        "ix_order_header_package_status_purchase",
        "order_header",
        ["package_status", "purchase_date"],
    )


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md §11")
