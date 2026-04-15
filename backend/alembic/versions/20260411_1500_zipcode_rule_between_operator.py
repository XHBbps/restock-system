"""zipcode_rule add between operator and widen columns

Revision ID: 20260411_1500
Revises: 20260411_1000
Create Date: 2026-04-11 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260411_1500"
down_revision: str | Sequence[str] | None = "20260411_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_operator_constraint_if_exists() -> None:
    op.execute("ALTER TABLE zipcode_rule DROP CONSTRAINT IF EXISTS operator_enum")
    op.execute("ALTER TABLE zipcode_rule DROP CONSTRAINT IF EXISTS ck_zipcode_rule_operator_enum")
    op.execute(
        "ALTER TABLE zipcode_rule DROP CONSTRAINT IF EXISTS "
        "ck_zipcode_rule_ck_zipcode_rule_operator_enum"
    )


def upgrade() -> None:
    op.alter_column(
        "zipcode_rule",
        "operator",
        existing_type=sa.String(length=5),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
    op.alter_column(
        "zipcode_rule",
        "compare_value",
        existing_type=sa.String(length=50),
        type_=sa.String(length=200),
        existing_nullable=False,
    )
    _drop_operator_constraint_if_exists()
    op.create_check_constraint(
        "operator_enum",
        "zipcode_rule",
        "operator IN ('=','!=','>','>=','<','<=','contains','not_contains','between')",
    )


def downgrade() -> None:
    _drop_operator_constraint_if_exists()
    op.create_check_constraint(
        "operator_enum",
        "zipcode_rule",
        "operator IN ('=','!=','>','>=','<','<=','contains','not_contains')",
    )
    op.alter_column(
        "zipcode_rule",
        "compare_value",
        existing_type=sa.String(length=200),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
    op.alter_column(
        "zipcode_rule",
        "operator",
        existing_type=sa.String(length=10),
        type_=sa.String(length=5),
        existing_nullable=False,
    )
