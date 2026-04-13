"""add scheduler_enabled to global_config

Revision ID: 20260409_1700
Revises: 20260409_0935
Create Date: 2026-04-09 17:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260409_1700"
down_revision: str | Sequence[str] | None = "20260409_0935"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "global_config",
        sa.Column("scheduler_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("global_config", "scheduler_enabled")
