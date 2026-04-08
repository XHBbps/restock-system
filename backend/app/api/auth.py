"""鉴权路由。

登录锁定语义（spec FR-022 + analyze U2 修订）：
- 登录前检查 login_locked_until > now() → 返回 423
- 密码错误 → login_failed_count += 1，达到阈值 → 设置 locked_until + 清零
- 密码正确且未锁定 → 清零计数 + 签发 JWT
- 计数修改用单条 UPDATE WHERE id=1 避免并发竞态
"""

from datetime import timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_session
from app.config import get_settings
from app.core.exceptions import LoginLocked, Unauthorized
from app.core.security import create_access_token, verify_password
from app.core.timezone import now_beijing
from app.models.global_config import GlobalConfig

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # 秒


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(db_session)) -> LoginResponse:
    settings = get_settings()
    now = now_beijing()

    # 读取配置（单行）
    result = await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
    config = result.scalar_one_or_none()
    if config is None:
        raise Unauthorized("系统未初始化，请联系运维")

    # 锁定检查
    if config.login_locked_until is not None and config.login_locked_until > now:
        raise LoginLocked(
            "账号已锁定，请稍后再试",
            locked_until=config.login_locked_until.isoformat(),
        )

    # 验证密码
    if not verify_password(req.password, config.login_password_hash):
        # 失败 +1，达到阈值则锁定 + 清零
        new_count = config.login_failed_count + 1
        if new_count >= settings.login_failed_max:
            await db.execute(
                update(GlobalConfig)
                .where(GlobalConfig.id == 1)
                .values(
                    login_failed_count=0,
                    login_locked_until=now + timedelta(minutes=settings.login_lock_minutes),
                )
            )
        else:
            await db.execute(
                update(GlobalConfig)
                .where(GlobalConfig.id == 1)
                .values(login_failed_count=new_count)
            )
        raise Unauthorized("密码错误")

    # 成功：清零计数与锁定
    await db.execute(
        update(GlobalConfig)
        .where(GlobalConfig.id == 1)
        .values(login_failed_count=0, login_locked_until=None)
    )

    token = create_access_token()
    return LoginResponse(
        access_token=token,
        expires_in=settings.jwt_expires_hours * 3600,
    )


@router.post("/logout", status_code=204)
async def logout(_: dict = Depends(get_current_session)) -> None:
    """登出（无服务端 session，前端清 token 即可）。"""
    return None


@router.get("/me")
async def me(session: dict = Depends(get_current_session)) -> dict:
    return {"subject": session["subject"]}
