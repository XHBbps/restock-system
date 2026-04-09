"""赛狐 access_token 管理。

特性：
- GET /api/oauth/v2/token.json 是唯一不走签名的 GET 接口
- 返回 expires_in 单位为毫秒（实测 ~24h）
- 缓存到 access_token_cache 表 + 内存
- 提前 5 分钟（settings.saihu_token_refresh_ahead_seconds）主动续期
- 收到 40001 时由 SaihuClient 调用 force_refresh()
- 不能频繁调用（赛狐另有限流）
"""

import asyncio
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.core.exceptions import SaihuAPIError
from app.core.logging import get_logger
from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.models.access_token import AccessTokenCache

logger = get_logger(__name__)


class TokenManager:
    """单例 token 管理器。"""

    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at: datetime | None = None
        self._lock = asyncio.Lock()
        self._refresh_future: asyncio.Future[str] | None = None
        self._refresh_task: asyncio.Task[None] | None = None

    async def get_token(self) -> str:
        """获取有效 token，必要时刷新。"""
        settings = get_settings()
        # 单飞（single-flight）：快速路径先检查内存，未命中再走共享刷新
        async with self._lock:
            if (
                self._token
                and self._expires_at
                and self._expires_at - now_beijing()
                > timedelta(seconds=settings.saihu_token_refresh_ahead_seconds)
            ):
                return self._token

            # Load DB cache only when in-memory token is absent, so stale DB
            # state cannot clobber a freshly refreshed in-memory token.
            if self._token is None:
                await self._load_from_db()
            if (
                self._token
                and self._expires_at
                and self._expires_at - now_beijing()
                > timedelta(seconds=settings.saihu_token_refresh_ahead_seconds)
            ):
                return self._token

            future = self._get_or_start_refresh_locked()
        return await future

    async def force_refresh(self) -> str:
        """收到 40001 时强制刷新（single-flight：多个并发调用共享同一次 HTTP 刷新）。"""
        async with self._lock:
            future = self._get_or_start_refresh_locked()
        return await future

    def _get_or_start_refresh_locked(self) -> "asyncio.Future[str]":
        """必须在持有 self._lock 时调用。返回当前进行中的刷新 future，或新建一个。"""
        if self._refresh_future is not None and not self._refresh_future.done():
            return self._refresh_future
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[str] = loop.create_future()
        self._refresh_future = fut
        # 后台任务在锁外执行真正的 HTTP 刷新
        self._refresh_task = asyncio.create_task(self._run_refresh(fut))
        return fut

    async def _run_refresh(self, fut: "asyncio.Future[str]") -> None:
        try:
            token = await self._refresh()
        except BaseException as exc:
            if not fut.done():
                fut.set_exception(exc)
        else:
            if not fut.done():
                fut.set_result(token)
        finally:
            async with self._lock:
                if self._refresh_future is fut:
                    self._refresh_future = None

    async def _load_from_db(self) -> None:
        async with async_session_factory() as db:
            row = await db.execute(select(AccessTokenCache).where(AccessTokenCache.id == 1))
            cache = row.scalar_one_or_none()
            if cache:
                self._token = cache.access_token
                self._expires_at = cache.expires_at

    async def _refresh(self) -> str:
        settings = get_settings()
        url = f"{settings.saihu_base_url}/api/oauth/v2/token.json"
        params = {
            "client_id": settings.saihu_client_id,
            "client_secret": settings.saihu_client_secret,
            "grant_type": "client_credentials",
        }
        logger.info("saihu_token_refresh_start")
        async with httpx.AsyncClient(timeout=settings.saihu_request_timeout_seconds) as client:
            resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise SaihuAPIError(
                f"获取 access_token HTTP 失败: {resp.status_code}", endpoint="oauth_token"
            )
        body = resp.json()
        if body.get("code") != 0:
            raise SaihuAPIError(
                f"获取 access_token 业务错误: {body.get('msg')}",
                endpoint="oauth_token",
                code=body.get("code"),
            )
        data = body.get("data") or {}
        token = data.get("access_token")
        expires_in_ms = int(data.get("expires_in", 0))
        if not token or expires_in_ms <= 0:
            raise SaihuAPIError("赛狐返回 token 字段缺失", endpoint="oauth_token")

        now = now_beijing()
        expires_at = now + timedelta(milliseconds=expires_in_ms)
        self._token = token
        self._expires_at = expires_at

        # 持久化（UPSERT 单行）
        async with async_session_factory() as db:
            stmt = pg_insert(AccessTokenCache).values(
                id=1,
                access_token=token,
                acquired_at=now,
                expires_at=expires_at,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[AccessTokenCache.id],
                set_={
                    "access_token": token,
                    "acquired_at": now,
                    "expires_at": expires_at,
                },
            )
            await db.execute(stmt)
            await db.commit()

        logger.info("saihu_token_refresh_ok", expires_at=expires_at.isoformat())
        return token


# 进程级单例
_token_manager: TokenManager | None = None


def get_token_manager() -> TokenManager:
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager
