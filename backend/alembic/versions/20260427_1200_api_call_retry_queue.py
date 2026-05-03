"""add precise retry queue fields to api_call_log.

Revision ID: 20260427_1200
Revises: 20260425_1420
Create Date: 2026-04-27 12:00:00

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260427_1200"
down_revision = "20260425_1420"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_call_log",
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("api_call_log", sa.Column("retry_status", sa.String(length=20), nullable=True))
    op.add_column(
        "api_call_log",
        sa.Column(
            "auto_retry_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "api_call_log",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "api_call_log",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "api_call_log",
        sa.Column("last_retry_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "api_call_log",
        sa.Column("retry_source_log_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_api_call_log_retry_source",
        "api_call_log",
        "api_call_log",
        ["retry_source_log_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_api_call_log_retry_queue",
        "api_call_log",
        ["next_retry_at", "called_at"],
        postgresql_where=sa.text(
            "saihu_code = 40019 AND retry_status = 'queued' "
            "AND request_payload IS NOT NULL AND retry_source_log_id IS NULL"
        ),
    )
    op.create_index(
        "ix_api_call_log_retry_source",
        "api_call_log",
        ["retry_source_log_id"],
    )
    op.execute(
        """
        UPDATE api_call_log
        SET retry_status = 'unsupported',
            last_retry_error = '历史调用日志未保存 request_payload，无法精确重试'
        WHERE saihu_code = 40019
          AND request_payload IS NULL
          AND retry_source_log_id IS NULL
        """
    )
    op.alter_column("api_call_log", "auto_retry_attempts", server_default=None)


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md §11")
