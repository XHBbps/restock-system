"""Add restock_regions to global_config.

Revision ID: 20260414_1500
Revises: 20260414_1300
Create Date: 2026-04-14 15:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260414_1500"
down_revision = "20260414_1300"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "global_config",
        sa.Column(
            "restock_regions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported. Restore from backup before rollback.")
