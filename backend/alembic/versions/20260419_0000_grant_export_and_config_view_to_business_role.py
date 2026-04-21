"""grant restock:export and config:view to business role

Revision ID: 20260419_0000
Revises: 20260418_0900
Create Date: 2026-04-19
"""

import sqlalchemy as sa

from alembic import op

revision = "20260419_0000"
down_revision = "20260418_0900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """幂等追加：业务人员 += restock:export, config:view。

    现有"业务人员"默认角色（20260414_2400 seed）不含 config:view / restock:export。
    前端补货单导出按钮和生成开关状态读取依赖这两条权限。
    ON CONFLICT DO NOTHING 保证已手动授予过的实例重入无副作用。
    """
    op.execute(
        sa.text(
            """
            INSERT INTO role_permission (role_id, permission_id)
            SELECT r.id, p.id
            FROM role r
            CROSS JOIN permission p
            WHERE r.name = '业务人员'
              AND p.code IN ('restock:export', 'config:view')
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM role_permission
            WHERE role_id = (SELECT id FROM role WHERE name = '业务人员')
              AND permission_id IN (
                SELECT id FROM permission WHERE code IN ('restock:export', 'config:view')
              )
            """
        )
    )
