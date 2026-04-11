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


def upgrade() -> None:
    # 1. 扩展列长度:operator 存得下 'between',compare_value 存得下多段区间
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
    # 2. 替换 CHECK 约束,加入 'between'
    op.drop_constraint("operator_enum", "zipcode_rule", type_="check")
    op.create_check_constraint(
        "operator_enum",
        "zipcode_rule",
        "operator IN ('=','!=','>','>=','<','<=','contains','not_contains','between')",
    )


def downgrade() -> None:
    # 注意:若存在 operator='between' 的行,downgrade 前必须手动清理,否则 CHECK 约束会失败
    op.drop_constraint("operator_enum", "zipcode_rule", type_="check")
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
