"""认证路由。"""

import ipaddress
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import UserContext, db_session, get_current_user
from app.config import get_settings
from app.core.exceptions import LoginLocked, Unauthorized
from app.core.logging import get_logger
from app.core.permissions import REGISTRY
from app.core.security import create_access_token, hash_password, verify_password
from app.core.timezone import now_beijing
from app.models.login_attempt import LoginAttempt
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.sys_user import SysUser
from app.schemas.auth import (
    ChangeOwnPassword,
    LoginRequest,
    LoginResponse,
    UserInfoResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = get_logger(__name__)

_TRUSTED_CIDRS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]


# ── helpers ──────────────────────────────────────────────────


def _get_login_source_key(request: Request) -> str:
    peer_ip = request.client.host if request.client else "unknown"
    try:
        addr = ipaddress.ip_address(peer_ip)
        is_trusted = any(addr in cidr for cidr in _TRUSTED_CIDRS)
    except ValueError:
        is_trusted = False

    if is_trusted:
        forwarded_for = request.headers.get("x-forwarded-for", "").strip()
        if forwarded_for:
            client_ip = forwarded_for.split(",", 1)[0].strip()
        else:
            client_ip = request.headers.get("x-real-ip", "").strip()
    else:
        client_ip = peer_ip

    if not client_ip:
        client_ip = "unknown"
    return f"ip:{client_ip}"


async def _build_user_info(
    db: AsyncSession,
    *,
    user_id: int,
    role_id: int,
    is_superadmin: bool,
    role_name: str,
    username: str,
    display_name: str,
    password_hash: str,
) -> UserInfoResponse:
    """构建 UserInfoResponse，login 和 /me 共用。"""
    if is_superadmin:
        permissions = [p.code for p in REGISTRY]
    else:
        rows = (
            await db.execute(
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role_id, Permission.active.is_(True))
            )
        ).scalars().all()
        permissions = list(rows)

    password_is_default = verify_password("admin123", password_hash)

    return UserInfoResponse(
        id=user_id,
        username=username,
        display_name=display_name,
        role_name=role_name,
        is_superadmin=is_superadmin,
        password_is_default=password_is_default,
        permissions=permissions,
    )


async def _check_lockout(db: AsyncSession, source_key: str, now) -> LoginAttempt | None:
    """检查某维度是否被锁定，返回该维度的 attempt 行（可能为 None）。"""
    attempt = (
        await db.execute(select(LoginAttempt).where(LoginAttempt.source_key == source_key))
    ).scalar_one_or_none()

    if attempt is not None and attempt.locked_until is not None and attempt.locked_until > now:
        logger.warning(
            "auth_login_blocked_locked",
            source_key=source_key,
            locked_until=attempt.locked_until.isoformat(),
        )
        raise LoginLocked(
            "当前来源已被临时锁定，请稍后再试", locked_until=attempt.locked_until.isoformat()
        )
    return attempt


async def _record_failure(
    db: AsyncSession, source_key: str, attempt: LoginAttempt | None, now
) -> None:
    """为某维度写入一条失败记录。"""
    settings = get_settings()
    current_failed = attempt.failed_count if attempt is not None else 0
    new_count = current_failed + 1
    locked_until = None
    failed_count = new_count
    if new_count >= settings.login_failed_max:
        failed_count = 0
        locked_until = now + timedelta(minutes=settings.login_lock_minutes)

    stmt = pg_insert(LoginAttempt).values(
        source_key=source_key,
        failed_count=failed_count,
        locked_until=locked_until,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[LoginAttempt.source_key],
        set_={
            "failed_count": failed_count,
            "locked_until": locked_until,
            "updated_at": now,
        },
    )
    await db.execute(stmt)

    if locked_until is not None:
        logger.warning(
            "auth_login_lockout_triggered",
            source_key=source_key,
            failed_count=settings.login_failed_max,
            lock_minutes=settings.login_lock_minutes,
            locked_until=locked_until.isoformat(),
        )
    else:
        logger.warning(
            "auth_login_failed",
            source_key=source_key,
            failed_count=new_count,
        )


async def _clear_attempts(db: AsyncSession, source_key: str, now) -> None:
    """登录成功后清除某维度的失败记录。"""
    await db.execute(
        update(LoginAttempt)
        .where(LoginAttempt.source_key == source_key)
        .values(failed_count=0, locked_until=None, updated_at=now)
    )


# ── routes ───────────────────────────────────────────────────


@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(db_session),
) -> LoginResponse:
    settings = get_settings()
    now = now_beijing()

    ip_key = _get_login_source_key(request)
    user_key = f"user:{req.username}"

    # 双维度锁定检查（任一维度锁定即拒绝）
    ip_attempt = await _check_lockout(db, ip_key, now)
    user_attempt = await _check_lockout(db, user_key, now)

    # 查找用户
    row = (
        await db.execute(
            select(
                SysUser.id,
                SysUser.username,
                SysUser.display_name,
                SysUser.password_hash,
                SysUser.is_active,
                SysUser.perm_version,
                SysUser.role_id,
                Role.is_superadmin,
                Role.name.label("role_name"),
            )
            .join(Role, SysUser.role_id == Role.id)
            .where(SysUser.username == req.username)
        )
    ).first()

    if row is None:
        # 用户不存在 — 仍记录失败（双维度）
        await _record_failure(db, ip_key, ip_attempt, now)
        await _record_failure(db, user_key, user_attempt, now)
        await db.commit()
        logger.warning("auth_login_failed", source_key=ip_key, reason="user_not_found")
        raise Unauthorized("用户名或密码错误")

    if not row.is_active:
        await _record_failure(db, ip_key, ip_attempt, now)
        await _record_failure(db, user_key, user_attempt, now)
        await db.commit()
        raise Unauthorized("用户名或密码错误")

    # 验证密码
    if not verify_password(req.password, row.password_hash):
        await _record_failure(db, ip_key, ip_attempt, now)
        await _record_failure(db, user_key, user_attempt, now)
        await db.commit()
        logger.warning("auth_login_failed", source_key=ip_key, username=req.username)
        raise Unauthorized("用户名或密码错误")

    # 登录成功 — 清除双维度失败记录
    if ip_attempt is not None and (ip_attempt.failed_count != 0 or ip_attempt.locked_until is not None):
        await _clear_attempts(db, ip_key, now)
    if user_attempt is not None and (user_attempt.failed_count != 0 or user_attempt.locked_until is not None):
        await _clear_attempts(db, user_key, now)

    # 更新 last_login_at
    await db.execute(
        update(SysUser).where(SysUser.id == row.id).values(last_login_at=now)
    )
    await db.commit()

    token = create_access_token(user_id=row.id, perm_version=row.perm_version)
    logger.info("auth_login_success", source_key=ip_key, user_id=row.id, username=row.username)

    user_info = await _build_user_info(
        db,
        user_id=row.id,
        role_id=row.role_id,
        is_superadmin=row.is_superadmin,
        role_name=row.role_name,
        username=row.username,
        display_name=row.display_name,
        password_hash=row.password_hash,
    )

    return LoginResponse(
        access_token=token,
        expires_in=settings.jwt_expires_hours * 3600,
        user=user_info,
    )


@router.post("/logout", status_code=204)
async def logout(_: UserContext = Depends(get_current_user)) -> None:
    return None


@router.get("/me", response_model=UserInfoResponse)
async def me(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
) -> UserInfoResponse:
    # 需要 password_hash 来判断是否默认密码
    row = (
        await db.execute(
            select(SysUser.password_hash).where(SysUser.id == user.id)
        )
    ).scalar_one()

    return await _build_user_info(
        db,
        user_id=user.id,
        role_id=user.role_id,
        is_superadmin=user.is_superadmin,
        role_name=user.role_name,
        username=user.username,
        display_name=user.display_name,
        password_hash=row,
    )


@router.put("/users/me/password")
async def change_own_password(
    body: ChangeOwnPassword,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(db_session),
) -> dict[str, str]:
    # 取当前密码哈希
    current_hash = (
        await db.execute(
            select(SysUser.password_hash).where(SysUser.id == user.id)
        )
    ).scalar_one()

    if not verify_password(body.old_password, current_hash):
        raise Unauthorized("旧密码错误")

    new_hash = hash_password(body.new_password)
    await db.execute(
        update(SysUser)
        .where(SysUser.id == user.id)
        .values(password_hash=new_hash, perm_version=SysUser.perm_version + 1)
    )
    await db.commit()

    return {"message": "密码修改成功"}
