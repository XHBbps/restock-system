"""认证路由。"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_session
from app.config import get_settings
from app.core.exceptions import LoginLocked, Unauthorized
from app.core.logging import get_logger
from app.core.security import create_access_token, verify_password
from app.core.timezone import now_beijing
from app.models.global_config import GlobalConfig
from app.models.login_attempt import LoginAttempt

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = get_logger(__name__)


class LoginRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def _get_login_source_key(request: Request) -> str:
    # 注:本函数无条件信任 X-Forwarded-For 首值,依赖 Caddy 反向代理通过
    # `header_up X-Forwarded-For {remote_host}` **覆盖**(而非 append)原 XFF
    # (见 deploy/Caddyfile 第 6 行),确保后端看到的是 Caddy 的真实对端 IP 而
    # 非客户端伪造值。若未来脱离 Caddy 直接暴露 backend,必须引入
    # TRUSTED_PROXIES 白名单校验 request.client.host 来源。
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        client_ip = forwarded_for.split(",", 1)[0].strip()
    else:
        client_ip = request.headers.get("x-real-ip", "").strip()
    if not client_ip and request.client is not None:
        client_ip = request.client.host
    return f"ip:{client_ip or 'unknown'}"


@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(db_session),
) -> LoginResponse:
    settings = get_settings()
    now = now_beijing()
    source_key = _get_login_source_key(request)

    config = (
        await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
    ).scalar_one_or_none()
    if config is None:
        raise Unauthorized("系统未初始化，请联系管理员")

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

    if not verify_password(req.password, config.login_password_hash):
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
        await db.commit()

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
        raise Unauthorized("密码错误")

    if attempt is not None and (attempt.failed_count != 0 or attempt.locked_until is not None):
        await db.execute(
            update(LoginAttempt)
            .where(LoginAttempt.source_key == source_key)
            .values(failed_count=0, locked_until=None, updated_at=now)
        )
        await db.commit()
        logger.info("auth_login_reset_after_success", source_key=source_key)

    token = create_access_token()
    logger.info("auth_login_success", source_key=source_key)
    return LoginResponse(
        access_token=token,
        expires_in=settings.jwt_expires_hours * 3600,
    )


@router.post("/logout", status_code=204)
async def logout(_: dict[str, Any] = Depends(get_current_session)) -> None:
    return None


@router.get("/me")
async def me(session: dict[str, Any] = Depends(get_current_session)) -> dict[str, Any]:
    return {"subject": session["subject"]}
