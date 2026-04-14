"""FastAPI 通用依赖。"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Forbidden, Unauthorized
from app.core.permission_cache import perm_cache
from app.core.permissions import ALL_CODES
from app.core.security import decode_token
from app.db.session import get_db
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.sys_user import SysUser


@dataclass
class UserContext:
    id: int
    username: str
    display_name: str
    role_id: int
    role_name: str
    is_superadmin: bool
    perm_version: int


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


_ALL_PERMISSIONS = frozenset(ALL_CODES)


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(db_session),
) -> UserContext:
    """从 JWT 中取出 user_id，查库验证用户状态和 perm_version。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("缺少 Authorization Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)
    if "sub" not in payload:
        raise Unauthorized("token 缺少 subject")

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise Unauthorized("token 无效")

    token_pv = payload.get("pv", -1)

    row = (
        await db.execute(
            select(
                SysUser.id,
                SysUser.username,
                SysUser.display_name,
                SysUser.is_active,
                SysUser.perm_version,
                SysUser.role_id,
                Role.is_superadmin,
                Role.name.label("role_name"),
            )
            .join(Role, SysUser.role_id == Role.id)
            .where(SysUser.id == user_id)
        )
    ).first()

    if row is None:
        raise Unauthorized("用户不存在")
    if not row.is_active:
        raise Unauthorized("账户已被禁用")
    if row.perm_version != token_pv:
        raise Unauthorized("会话已过期，请重新登录")

    return UserContext(
        id=row.id,
        username=row.username,
        display_name=row.display_name,
        role_id=row.role_id,
        role_name=row.role_name,
        is_superadmin=row.is_superadmin,
        perm_version=row.perm_version,
    )


async def get_current_permissions(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
) -> frozenset[str]:
    """返回当前用户的权限 code 集合，超管返回全量。"""
    if user.is_superadmin:
        return _ALL_PERMISSIONS

    cached = perm_cache.get(user.id, user.perm_version)
    if cached is not None:
        return cached

    rows = (
        await db.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == user.role_id, Permission.active.is_(True))
        )
    ).scalars().all()

    perms = frozenset(rows)
    perm_cache.set(user.id, user.perm_version, perms)
    return perms


def require_permission(*codes: str):
    """路由级权限检查工厂（AND 语义：所有 codes 必须满足）。"""
    async def _checker(
        permissions: frozenset[str] = Depends(get_current_permissions),
    ) -> None:
        for code in codes:
            if code not in permissions:
                raise Forbidden("权限不足")
    return _checker


__all__ = [
    "Depends",
    "UserContext",
    "db_session",
    "get_current_permissions",
    "get_current_user",
    "require_permission",
]
