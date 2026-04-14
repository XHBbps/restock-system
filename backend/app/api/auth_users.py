"""用户管理路由。"""

from fastapi import APIRouter, Depends
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import UserContext, db_session, get_current_user, require_permission
from app.core.exceptions import BusinessError, ConflictError, NotFound
from app.core.logging import get_logger
from app.core.permissions import AUTH_MANAGE, AUTH_VIEW
from app.core.security import hash_password
from app.models.role import Role
from app.models.sys_user import SysUser
from app.schemas.auth import (
    PasswordReset,
    UserCreate,
    UserOut,
    UserStatusPatch,
    UserUpdate,
)

router = APIRouter(prefix="/api/auth/users", tags=["auth-users"])
logger = get_logger(__name__)


# ── helpers ──────────────────────────────────────────────────


async def _check_last_superadmin(db: AsyncSession, user_id: int) -> None:
    """Raise if user_id is the only active superadmin user."""
    count = (
        await db.execute(
            select(func.count())
            .select_from(SysUser)
            .join(Role, SysUser.role_id == Role.id)
            .where(Role.is_superadmin.is_(True), SysUser.is_active.is_(True), SysUser.id != user_id)
        )
    ).scalar()
    if count == 0:
        raise BusinessError("至少需要保留一个超管用户")


def _user_to_out(row) -> UserOut:
    """Convert a joined query row (sys_user + role) to UserOut."""
    return UserOut(
        id=row.id,
        username=row.username,
        display_name=row.display_name,
        role_id=row.role_id,
        role_name=row.role_name,
        is_active=row.is_active,
        is_superadmin=row.is_superadmin,
        last_login_at=row.last_login_at,
    )


def _user_select():
    """Common select for user + role join."""
    return (
        select(
            SysUser.id,
            SysUser.username,
            SysUser.display_name,
            SysUser.role_id,
            SysUser.is_active,
            SysUser.last_login_at,
            Role.name.label("role_name"),
            Role.is_superadmin,
        )
        .join(Role, SysUser.role_id == Role.id)
    )


# ── routes ───────────────────────────────────────────────────


@router.get(
    "",
    response_model=list[UserOut],
    dependencies=[Depends(require_permission(AUTH_VIEW))],
)
async def list_users(
    db: AsyncSession = Depends(db_session),
) -> list[UserOut]:
    rows = (await db.execute(_user_select())).all()
    return [_user_to_out(r) for r in rows]


@router.post(
    "",
    response_model=UserOut,
    status_code=201,
    dependencies=[Depends(require_permission(AUTH_MANAGE))],
)
async def create_user(
    body: UserCreate,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
) -> UserOut:
    # Check username uniqueness
    exists = (
        await db.execute(select(SysUser.id).where(SysUser.username == body.username))
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError(f"用户名 '{body.username}' 已存在")

    # Check role exists
    role = (
        await db.execute(select(Role.id, Role.name).where(Role.id == body.role_id))
    ).first()
    if role is None:
        raise NotFound("角色不存在")

    new_user = SysUser(
        username=body.username,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        role_id=body.role_id,
    )
    db.add(new_user)
    await db.flush()

    logger.info(
        "auth_user_created",
        target_username=body.username,
        role_name=role.name,
        operator_id=user.id,
    )

    # Re-query to get full joined row
    row = (await db.execute(_user_select().where(SysUser.id == new_user.id))).first()
    await db.commit()
    return _user_to_out(row)


@router.put(
    "/{user_id}",
    response_model=UserOut,
    dependencies=[Depends(require_permission(AUTH_MANAGE))],
)
async def update_user(
    user_id: int,
    body: UserUpdate,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
) -> UserOut:
    # Check user exists
    target = (
        await db.execute(
            select(SysUser.id, SysUser.role_id, Role.name.label("role_name"), Role.is_superadmin)
            .join(Role, SysUser.role_id == Role.id)
            .where(SysUser.id == user_id)
        )
    ).first()
    if target is None:
        raise NotFound("用户不存在")

    values: dict = {}
    if body.display_name is not None:
        values["display_name"] = body.display_name

    if body.role_id is not None and body.role_id != target.role_id:
        # Check new role exists
        new_role = (
            await db.execute(select(Role.id, Role.name, Role.is_superadmin).where(Role.id == body.role_id))
        ).first()
        if new_role is None:
            raise NotFound("角色不存在")

        # Last superadmin protection
        if target.is_superadmin and not new_role.is_superadmin:
            await _check_last_superadmin(db, user_id)

        values["role_id"] = body.role_id
        values["perm_version"] = SysUser.perm_version + 1

        logger.info(
            "auth_user_role_changed",
            target_username=target.id,
            old_role=target.role_name,
            new_role=new_role.name,
            operator_id=user.id,
        )

    if values:
        await db.execute(update(SysUser).where(SysUser.id == user_id).values(**values))

    row = (await db.execute(_user_select().where(SysUser.id == user_id))).first()
    await db.commit()
    return _user_to_out(row)


@router.delete(
    "/{user_id}",
    status_code=204,
    dependencies=[Depends(require_permission(AUTH_MANAGE))],
)
async def delete_user(
    user_id: int,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
) -> None:
    # Check user exists
    target = (
        await db.execute(
            select(SysUser.id, SysUser.username, Role.is_superadmin)
            .join(Role, SysUser.role_id == Role.id)
            .where(SysUser.id == user_id)
        )
    ).first()
    if target is None:
        raise NotFound("用户不存在")

    if user_id == user.id:
        raise BusinessError("不能删除自己的账户")

    if target.is_superadmin:
        await _check_last_superadmin(db, user_id)

    await db.execute(delete(SysUser).where(SysUser.id == user_id))
    await db.commit()

    logger.info(
        "auth_user_deleted",
        target_username=target.username,
        operator_id=user.id,
    )


@router.patch(
    "/{user_id}/status",
    response_model=UserOut,
    dependencies=[Depends(require_permission(AUTH_MANAGE))],
)
async def toggle_user_status(
    user_id: int,
    body: UserStatusPatch,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
) -> UserOut:
    target = (
        await db.execute(
            select(SysUser.id, SysUser.username, SysUser.is_active, Role.is_superadmin)
            .join(Role, SysUser.role_id == Role.id)
            .where(SysUser.id == user_id)
        )
    ).first()
    if target is None:
        raise NotFound("用户不存在")

    if user_id == user.id and not body.is_active:
        raise BusinessError("不能禁用自己的账户")

    if not body.is_active and target.is_superadmin:
        await _check_last_superadmin(db, user_id)

    await db.execute(
        update(SysUser).where(SysUser.id == user_id).values(is_active=body.is_active)
    )

    event = "auth_user_enabled" if body.is_active else "auth_user_disabled"
    logger.info(event, target_username=target.username, operator_id=user.id)

    row = (await db.execute(_user_select().where(SysUser.id == user_id))).first()
    await db.commit()
    return _user_to_out(row)


@router.put(
    "/{user_id}/password",
    status_code=204,
    dependencies=[Depends(require_permission(AUTH_MANAGE))],
)
async def reset_password(
    user_id: int,
    body: PasswordReset,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
) -> None:
    target = (
        await db.execute(select(SysUser.id, SysUser.username).where(SysUser.id == user_id))
    ).first()
    if target is None:
        raise NotFound("用户不存在")

    await db.execute(
        update(SysUser)
        .where(SysUser.id == user_id)
        .values(
            password_hash=hash_password(body.new_password),
            perm_version=SysUser.perm_version + 1,
        )
    )
    await db.commit()

    logger.info(
        "auth_password_reset",
        target_username=target.username,
        operator_id=user.id,
    )
