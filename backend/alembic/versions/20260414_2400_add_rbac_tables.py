"""add RBAC tables (role, permission, role_permission, sys_user) with seed data

Revision ID: 20260414_2400
Revises: 20260414_2300
Create Date: 2026-04-14 24:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.permissions import REGISTRY
from app.core.security import hash_password

revision: str = "20260414_2400"
down_revision: str | Sequence[str] | None = "20260414_2300"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. role ──────────────────────────────────────────────
    op.create_table(
        "role",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("is_superadmin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_role"),
        sa.UniqueConstraint("name", name="uq_role_name"),
    )

    # ── 2. permission ────────────────────────────────────────
    op.create_table(
        "permission",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("group_name", sa.String(length=50), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_permission"),
        sa.UniqueConstraint("code", name="uq_permission_code"),
    )

    # ── 3. role_permission ───────────────────────────────────
    op.create_table(
        "role_permission",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name="pk_role_permission"),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], name="fk_role_permission_role_id_role", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["permission_id"], ["permission.id"], name="fk_role_permission_permission_id_permission", ondelete="CASCADE"
        ),
    )

    # ── 4. sys_user ──────────────────────────────────────────
    op.create_table(
        "sys_user",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("perm_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sys_user"),
        sa.UniqueConstraint("username", name="uq_sys_user_username"),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], name="fk_sys_user_role_id_role", ondelete="RESTRICT"),
    )
    op.create_index("ix_sys_user_role_id", "sys_user", ["role_id"])

    # ── 5. Seed permissions from REGISTRY ────────────────────
    perm_table = sa.table(
        "permission",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("group_name", sa.String),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        perm_table,
        [
            {"code": p.code, "name": p.name, "group_name": p.group_name, "sort_order": i}
            for i, p in enumerate(REGISTRY)
        ],
    )

    # ── 6. Seed roles ────────────────────────────────────────
    role_table = sa.table(
        "role",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("is_superadmin", sa.Boolean),
    )
    op.bulk_insert(
        role_table,
        [
            {"id": 1, "name": "超级管理员", "description": "拥有全部权限", "is_superadmin": True},
            {"id": 2, "name": "阅读者", "description": "可查看除系统设置外的所有数据", "is_superadmin": False},
            {"id": 3, "name": "业务人员", "description": "可操作补货发起并查看业务数据", "is_superadmin": False},
        ],
    )

    # ── 7. Seed role_permissions ─────────────────────────────
    conn = op.get_bind()

    reader_codes = ["home:view", "restock:view", "history:view", "data_base:view", "data_biz:view"]
    operator_codes = reader_codes + ["restock:operate", "history:delete"]

    # Query permission IDs by code
    perm_id_rows = conn.execute(
        sa.text("SELECT id, code FROM permission WHERE code = ANY(:codes)"),
        {"codes": list(set(operator_codes))},
    ).fetchall()
    code_to_id = {row[1]: row[0] for row in perm_id_rows}

    rp_table = sa.table(
        "role_permission",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )

    # Role 2 - 阅读者
    rp_rows = [{"role_id": 2, "permission_id": code_to_id[c]} for c in reader_codes]
    # Role 3 - 业务人员
    rp_rows += [{"role_id": 3, "permission_id": code_to_id[c]} for c in operator_codes]

    op.bulk_insert(rp_table, rp_rows)

    # ── 8. Seed admin user ───────────────────────────────────
    user_table = sa.table(
        "sys_user",
        sa.column("username", sa.String),
        sa.column("display_name", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("role_id", sa.Integer),
    )
    op.bulk_insert(
        user_table,
        [
            {
                "username": "admin",
                "display_name": "管理员",
                "password_hash": hash_password("admin123"),
                "role_id": 1,
            }
        ],
    )

    # NOTE: global_config.login_password_hash is DEPRECATED, replaced by sys_user.password_hash


def downgrade() -> None:
    op.drop_table("sys_user")
    op.drop_table("role_permission")
    op.drop_table("permission")
    op.drop_table("role")
