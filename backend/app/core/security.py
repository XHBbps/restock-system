"""密码哈希与 JWT 工具。"""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.config import get_settings
from app.core.exceptions import Unauthorized


def hash_password(plain: str) -> str:
    """生成密码 bcrypt 哈希。"""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """验证密码哈希。"""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(subject: str = "owner", extra: dict[str, Any] | None = None) -> str:
    """签发 JWT。

    单用户场景下 subject 固定为 'owner',可在 extra 中放入额外声明。
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=settings.jwt_expires_hours)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """解码 + 校验 JWT,失败抛 Unauthorized。"""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise Unauthorized("token 无效或已过期") from exc
