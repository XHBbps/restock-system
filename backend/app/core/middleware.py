"""HTTP 请求结构化日志中间件。

每个请求生成 request_id（structlog contextvar 绑定），记录方法、路径、
状态、耗时；4xx/5xx 单独高亮。
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        started = time.monotonic()
        try:
            response: Response = await call_next(request)
        except Exception:
            duration_ms = int((time.monotonic() - started) * 1000)
            logger.exception(
                "http_request_exception",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
            raise

        duration_ms = int((time.monotonic() - started) * 1000)
        log_method = logger.info if response.status_code < 400 else logger.warning
        log_method(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers["X-Request-Id"] = request_id
        return response
