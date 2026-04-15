"""extend zipcode_rule operator enum

Revision ID: 20260410_1300
Revises: 20260409_1710
Create Date: 2026-04-10 13:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260410_1300"
down_revision: str | Sequence[str] | None = "20260410_0002"
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
    _drop_operator_constraint_if_exists()
    op.create_check_constraint(
        "operator_enum",
        "zipcode_rule",
        "operator IN ('=','!=','>','>=','<','<=','contains','not_contains')",
    )


def downgrade() -> None:
    _drop_operator_constraint_if_exists()
    op.create_check_constraint(
        "operator_enum",
        "zipcode_rule",
        "operator IN ('=','!=','>','>=','<','<=')",
    )
