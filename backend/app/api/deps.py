"""FastAPI 通用依赖。"""

from collections.abc import AsyncGenerator

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Unauthorized
from app.core.security import decode_token
from app.db.session import get_db


async def get_current_session(
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    """从 Authorization Bearer 中取出 JWT 并校验。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("缺少 Authorization Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)
    if "sub" not in payload:
        raise Unauthorized("token 缺少 subject")
    return {"subject": payload["sub"]}


# 同步会话依赖的类型别名（方便路由签名书写）
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


__all__ = ["get_current_session", "db_session", "Depends"]
