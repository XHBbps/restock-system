"""简易内存速率限制中间件（零外部依赖）。

按客户端 IP 限制请求频率。使用 Caddy 覆盖后的 X-Forwarded-For
作为 IP 源（见 deploy/Caddyfile header_up 配置说明）。

设计约束：
- 内存存储，进程重启即清空（单进程部署可接受）
- 不跨 worker/scheduler 容器共享（各进程独立限流）
- 对 /healthz、/readyz 探针请求不限流
"""

from collections import defaultdict
from time import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# 不限流的路径前缀
_EXEMPT_PATHS = ("/healthz", "/readyz")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """按 IP 滑动窗口限流。默认每 IP 每分钟 60 个请求。"""

    def __init__(
        self,
        app,  # type: ignore[no-untyped-def]
        max_requests: int = 60,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        if any(path.startswith(p) for p in _EXEMPT_PATHS):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = time()
        cutoff = now - self.window_seconds

        # 清理过期记录 + 释放空 key（防公网 bot 扫描导致 dict 无限膨胀）
        timestamps = self._requests[client_ip]
        active = [t for t in timestamps if t > cutoff]
        if not active:
            self._requests.pop(client_ip, None)
            active = []
        else:
            self._requests[client_ip] = active

        if len(active) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"status": "error", "message": "请求过于频繁，请稍后再试"},
            )

        self._requests[client_ip].append(now)
        return await call_next(request)

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "").strip()
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip
        if request.client:
            return request.client.host
        return "unknown"
