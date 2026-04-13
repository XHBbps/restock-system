"""赛狐 API 业务接口客户端。

特性:
- 自动签名 + 注入公共 query 参数
- 每接口独立 1 QPS 限流
- tenacity 指数退避重试(针对网络/限流)
- 收到 40001 自动刷 token + 重试一次
- 每次调用结束写 api_call_log
"""

import asyncio
import random
import time
from typing import Any

import httpx
from sqlalchemy import insert
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.core.exceptions import (
    SaihuAPIError,
    SaihuAuthExpired,
    SaihuBizError,
    SaihuNetworkError,
    SaihuRateLimited,
)
from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.models.api_call_log import ApiCallLog
from app.saihu.rate_limit import get_limiter
from app.saihu.sign import generate_sign, make_nonce, make_timestamp_ms
from app.saihu.token import get_token_manager

logger = get_logger(__name__)


class SaihuClient:
    """赛狐业务接口客户端单例。"""

    def __init__(self) -> None:
        self._http: httpx.AsyncClient | None = None

    async def _ensure_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            settings = get_settings()
            self._http = httpx.AsyncClient(
                base_url=settings.saihu_base_url,
                timeout=settings.saihu_request_timeout_seconds,
            )
        return self._http

    async def close(self) -> None:
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()

    async def post(
        self,
        endpoint_path: str,
        body: dict[str, Any] | None = None,
        *,
        retry_network_errors: bool = True,
    ) -> dict[str, Any]:
        """发起一次 POST 业务请求并返回 data 字段。

        40001(token 失效)不占用正常的 tenacity 重试预算:在外层
        捕获一次,force_refresh 后重试一次;若再次 40001 或其他可重试
        错误则交给 tenacity 处理。
        """
        settings = get_settings()
        body = body or {}

        async def _retrying_call() -> dict[str, Any]:
            retry_types: tuple[type[Exception], ...]
            if retry_network_errors:
                retry_types = (SaihuRateLimited, SaihuNetworkError)
            else:
                retry_types = (SaihuRateLimited,)
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(settings.saihu_max_retries),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                retry=retry_if_exception_type(retry_types),
                reraise=True,
            ):
                with attempt:
                    return await self._do_request(
                        endpoint_path, body, attempt.retry_state.attempt_number
                    )
            # AsyncRetrying 总会抛或返回,这里不可达
            raise SaihuAPIError("unreachable", endpoint=endpoint_path)

        try:
            return await _retrying_call()
        except SaihuAuthExpired:
            # token 失效:force_refresh 已在 _do_request 里触发过;
            # 这里在 tenacity 预算之外再给一次完整的重试机会。
            logger.info("saihu_auth_expired_retry_outside_budget", endpoint=endpoint_path)
            # Small backoff to avoid hammering the token endpoint.
            await asyncio.sleep(0.3 + random.random() * 0.4)  # P1-6: 0.3-0.7s jitter
            return await _retrying_call()

    async def _do_request(
        self,
        endpoint_path: str,
        body: dict[str, Any],
        attempt_no: int,
    ) -> dict[str, Any]:
        settings = get_settings()
        token_mgr = get_token_manager()
        token = await token_mgr.get_token()

        nonce = make_nonce()
        timestamp = make_timestamp_ms()
        sign = generate_sign(
            access_token=token,
            client_id=settings.saihu_client_id,
            method="post",
            nonce=nonce,
            timestamp=timestamp,
            url=endpoint_path,
            client_secret=settings.saihu_client_secret,
        )
        params = {
            "access_token": token,
            "client_id": settings.saihu_client_id,
            "timestamp": timestamp,
            "nonce": nonce,
            "sign": sign,
        }

        limiter = get_limiter(endpoint_path)
        http = await self._ensure_http()
        started = time.monotonic()
        http_status: int | None = None
        saihu_code: int | None = None
        saihu_msg: str | None = None
        request_id: str | None = None
        error_type: str | None = None

        async with limiter:
            try:
                resp = await http.post(
                    endpoint_path,
                    params=params,
                    json=body,
                    headers={"Content-Type": "application/json"},
                )
                http_status = resp.status_code
            except httpx.RequestError as exc:
                error_type = "network"
                await self._log(
                    endpoint_path,
                    started,
                    http_status,
                    None,
                    str(exc),
                    None,
                    error_type,
                    attempt_no,
                )
                raise SaihuNetworkError(f"网络错误: {exc}", endpoint=endpoint_path) from exc

        try:
            payload = resp.json()
        except ValueError as exc:
            error_type = "biz_error"
            await self._log(
                endpoint_path,
                started,
                http_status,
                None,
                "invalid json",
                None,
                error_type,
                attempt_no,
            )
            raise SaihuBizError(f"赛狐返回非 JSON: {exc}", endpoint=endpoint_path) from exc

        saihu_code = payload.get("code")
        saihu_msg = payload.get("msg")
        request_id = payload.get("requestId")

        if saihu_code == 40001:
            error_type = "auth_fail"
            await self._log(
                endpoint_path,
                started,
                http_status,
                saihu_code,
                saihu_msg,
                request_id,
                error_type,
                attempt_no,
            )
            await get_token_manager().force_refresh()
            raise SaihuAuthExpired(
                "token 失效", endpoint=endpoint_path, code=saihu_code, request_id=request_id
            )

        if saihu_code == 40019:
            error_type = "rate_limit"
            await self._log(
                endpoint_path,
                started,
                http_status,
                saihu_code,
                saihu_msg,
                request_id,
                error_type,
                attempt_no,
            )
            raise SaihuRateLimited(
                "被限流", endpoint=endpoint_path, code=saihu_code, request_id=request_id
            )

        if saihu_code != 0:
            error_type = "biz_error"
            await self._log(
                endpoint_path,
                started,
                http_status,
                saihu_code,
                saihu_msg,
                request_id,
                error_type,
                attempt_no,
            )
            raise SaihuBizError(
                f"赛狐业务错误 code={saihu_code} msg={saihu_msg}",
                endpoint=endpoint_path,
                code=saihu_code,
                request_id=request_id,
            )

        await self._log(
            endpoint_path, started, http_status, saihu_code, saihu_msg, request_id, None, attempt_no
        )
        return payload

    async def _log(
        self,
        endpoint: str,
        started: float,
        http_status: int | None,
        saihu_code: int | None,
        saihu_msg: str | None,
        request_id: str | None,
        error_type: str | None,
        attempt_no: int,
    ) -> None:
        duration_ms = int((time.monotonic() - started) * 1000)
        try:
            async with async_session_factory() as db:
                await db.execute(
                    insert(ApiCallLog).values(
                        endpoint=endpoint,
                        method="POST",
                        duration_ms=duration_ms,
                        http_status=http_status,
                        saihu_code=saihu_code,
                        saihu_msg=saihu_msg,
                        request_id=request_id,
                        error_type=error_type,
                        retry_count=attempt_no - 1,
                    )
                )
                await db.commit()
        except Exception as exc:
            # 日志写入失败不应阻断业务
            logger.warning(
                "api_call_log_write_failed",
                error=str(exc),
                endpoint=endpoint,
                log_write_failed=True,
            )


# 进程级单例
_client: SaihuClient | None = None


def get_saihu_client() -> SaihuClient:
    global _client
    if _client is None:
        _client = SaihuClient()
    return _client
