"""add dashboard snapshot cache

Revision ID: 20260414_2300
Revises: 20260414_2100
Create Date: 2026-04-14 23:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260414_2300"
down_revision = "20260414_2100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dashboard_snapshot",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="empty"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_refresh_error", sa.Text(), nullable=True),
        sa.Column("refresh_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('empty','ready','refreshing','failed')",
            name=op.f("ck_dashboard_snapshot_dashboard_snapshot_status_enum"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dashboard_snapshot")),
    )
    op.execute("INSERT INTO dashboard_snapshot (id, status) VALUES (1, 'empty')")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported")
