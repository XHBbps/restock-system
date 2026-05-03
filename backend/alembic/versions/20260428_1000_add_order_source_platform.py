"""add order source and platform fields.

Revision ID: 20260428_1000
Revises: 20260427_1800
Create Date: 2026-04-28 10:00:00

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260428_1000"
down_revision = "20260427_1800"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_header",
        sa.Column(
            "source",
            sa.String(length=20),
            server_default="亚马逊",
            nullable=False,
        ),
    )
    op.add_column(
        "order_header",
        sa.Column(
            "order_platform",
            sa.String(length=50),
            server_default="亚马逊",
            nullable=False,
        ),
    )
    op.drop_constraint("uq_order_header_key", "order_header", type_="unique")
    op.create_unique_constraint(
        "uq_order_header_key",
        "order_header",
        ["shop_id", "amazon_order_id", "source"],
    )

    op.add_column(
        "order_detail",
        sa.Column(
            "source",
            sa.String(length=20),
            server_default="亚马逊",
            nullable=False,
        ),
    )
    op.drop_constraint("pk_order_detail", "order_detail", type_="primary")
    op.create_primary_key(
        "pk_order_detail",
        "order_detail",
        ["shop_id", "amazon_order_id", "source"],
    )

    op.add_column(
        "order_detail_fetch_log",
        sa.Column(
            "source",
            sa.String(length=20),
            server_default="亚马逊",
            nullable=False,
        ),
    )
    op.drop_constraint(
        "pk_order_detail_fetch_log",
        "order_detail_fetch_log",
        type_="primary",
    )
    op.create_primary_key(
        "pk_order_detail_fetch_log",
        "order_detail_fetch_log",
        ["shop_id", "amazon_order_id", "source"],
    )


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md §11")
