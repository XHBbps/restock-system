"""角色管理路由。"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import UserContext, db_session, get_current_user, require_permission
from app.core.exceptions import BusinessError, ConflictError, NotFound
from app.core.logging import get_logger
from app.core.permissions import AUTH_MANAGE, AUTH_VIEW
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.sys_user import SysUser
from app.schemas.auth import (
    PermissionOut,
    RoleCreate,
    RoleOut,
    RolePermissionUpdate,
    RoleUpdate,
)

router = APIRouter(prefix="/api/auth", tags=["auth-roles"])
logger = get_logger(__name__)


# ── helpers ──────────────────────────────────────────────────


def _role_list_select() -> Any:
    """Select roles with user_count."""
    return (
        select(
            Role.id,
            Role.name,
            Role.description,
            Role.is_superadmin,
            func.count(SysUser.id).label("user_count"),
        )
        .outerjoin(SysUser, SysUser.role_id == Role.id)
        .group_by(Role.id)
    )


async def _get_role_or_404(db: AsyncSession, role_id: int) -> Role:
    """Fetch role by id or raise NotFound."""
    role = (
        await db.execute(select(Role).where(Role.id == role_id))
    ).scalar_one_or_none()
    if role is None:
        raise NotFound("角色不存在")
    return role


# ── routes ───────────────────────────────────────────────────


@router.get(
    "/roles",
    response_model=list[RoleOut],
    dependencies=[Depends(require_permission(AUTH_VIEW))],
)
async def list_roles(
    db: AsyncSession = Depends(db_session),
) -> list[RoleOut]:
    rows = (await db.execute(_role_list_select())).all()
    return [RoleOut.model_validate(r, from_attributes=True) for r in rows]


@router.post(
    "/roles",
    response_model=RoleOut,
    status_code=201,
    dependencies=[Depends(require_permission(AUTH_MANAGE))],
)
async def create_role(
    body: RoleCreate,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
) -> RoleOut:
    # Check name uniqueness
    exists = (
        await db.execute(select(Role.id).where(Role.name == body.name))
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError(f"角色名 '{body.name}' 已存在")

    new_role = Role(
        name=body.name,
        description=body.description,
        is_superadmin=False,
    )
    db.add(new_role)
    await db.flush()

    logger.info(
        "auth_role_created",
        role_name=body.name,
        operator_id=user.id,
    )

    await db.commit()
    return RoleOut(
        id=new_role.id,
        name=new_role.name,
        description=new_role.description,
        is_superadmin=False,
        user_count=0,
    )


@router.put(
    "/roles/{role_id}",
    response_model=RoleOut,
    dependencies=[Depends(require_permission(AUTH_MANAGE))],
)
async def update_role(
    role_id: int,
    body: RoleUpdate,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
) -> RoleOut:
    role = await _get_role_or_404(db, role_id)

    if role.is_superadmin:
        raise BusinessError("系统内置角色不可编辑")

    values: dict[str, str] = {}
    if body.name is not None:
        values["name"] = body.name
    if body.description is not None:
        values["description"] = body.description

    if values:
        if "name" in values and values["name"] != role.name:
            logger.info(
                "auth_role_name_changed",
                old_name=role.name,
                new_name=values["name"],
                operator_id=user.id,
            )
        await db.execute(update(Role).where(Role.id == role_id).values(**values))

    row = (await db.execute(_role_list_select().where(Role.id == role_id))).first()
    await db.commit()
    return RoleOut.model_validate(row, from_attributes=True)


@router.delete(
    "/roles/{role_id}",
    status_code=204,
    dependencies=[Depends(require_permission(AUTH_MANAGE))],
)
async def delete_role(
    role_id: int,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
) -> None:
    role = await _get_role_or_404(db, role_id)

    if role.is_superadmin:
        raise BusinessError("系统内置角色不可删除")

    # Check no users assigned
    user_count = (
        await db.execute(
            select(func.count()).select_from(SysUser).where(SysUser.role_id == role_id)
        )
    ).scalar() or 0
    if user_count > 0:
        raise BusinessError("该角色下有用户，无法删除")

    await db.execute(delete(Role).where(Role.id == role_id))
    await db.commit()

    logger.info(
        "auth_role_deleted",
        role_name=role.name,
        operator_id=user.id,
    )


@router.get(
    "/roles/{role_id}/permissions",
    response_model=list[str],
    dependencies=[Depends(require_permission(AUTH_VIEW))],
)
async def get_role_permissions(
    role_id: int,
    db: AsyncSession = Depends(db_session),
) -> list[str]:
    await _get_role_or_404(db, role_id)

    rows = (
        await db.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id, Permission.active.is_(True))
        )
    ).scalars().all()
    return list(rows)


@router.put(
    "/roles/{role_id}/permissions",
    status_code=204,
    dependencies=[Depends(require_permission(AUTH_MANAGE))],
)
async def update_role_permissions(
    role_id: int,
    body: RolePermissionUpdate,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
) -> None:
    role = await _get_role_or_404(db, role_id)

    if role.is_superadmin:
        raise BusinessError("超管角色权限不可修改")

    # Get old permission codes for logging
    old_codes = set(
        (
            await db.execute(
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role_id)
            )
        ).scalars().all()
    )

    new_codes = set(body.permission_codes)

    # Resolve permission codes to IDs
    if new_codes:
        perm_rows = (
            await db.execute(
                select(Permission.id, Permission.code).where(
                    Permission.code.in_(new_codes), Permission.active.is_(True)
                )
            )
        ).all()
        found_codes = {r.code for r in perm_rows}
        missing = new_codes - found_codes
        if missing:
            raise BusinessError(f"权限代码不存在: {', '.join(sorted(missing))}")
        perm_ids = [r.id for r in perm_rows]
    else:
        perm_ids = []

    # Delete existing role_permission rows
    await db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))

    # Insert new rows
    for pid in perm_ids:
        db.add(RolePermission(role_id=role_id, permission_id=pid))

    # Bump perm_version for affected users
    await db.execute(
        update(SysUser)
        .where(SysUser.role_id == role_id)
        .values(perm_version=SysUser.perm_version + 1)
    )

    await db.commit()

    added = new_codes - old_codes
    removed = old_codes - new_codes
    logger.info(
        "auth_role_permissions_changed",
        role_name=role.name,
        added=sorted(added),
        removed=sorted(removed),
        operator_id=user.id,
    )


@router.get(
    "/permissions",
    response_model=list[PermissionOut],
    dependencies=[Depends(require_permission(AUTH_VIEW))],
)
async def list_permissions(
    db: AsyncSession = Depends(db_session),
) -> list[PermissionOut]:
    rows = (
        await db.execute(
            select(Permission.code, Permission.name, Permission.group_name)
            .where(Permission.active.is_(True))
            .order_by(Permission.sort_order)
        )
    ).all()
    return [PermissionOut.model_validate(r, from_attributes=True) for r in rows]
