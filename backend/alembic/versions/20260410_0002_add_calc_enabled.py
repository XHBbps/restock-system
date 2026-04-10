"""Add calc_enabled to global_config.

Revision ID: 20260410_0002
Revises: 20260410_0001
Create Date: 2026-04-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260410_0002"
down_revision: str | Sequence[str] | None = "20260410_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "global_config",
        sa.Column(
            "calc_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("global_config", "calc_enabled")
