"""简易内存速率限制中间件（零外部依赖）。

按客户端 IP 限制请求频率，优先使用 Caddy 透传的 `X-Forwarded-For`。
设计约束：
- 内存存储，进程重启即清空（单机部署可接受）
- 不跨 worker/scheduler 容器共享（各进程独立限流）
- `/healthz`、`/readyz` 健康探针不受限流
"""

import ipaddress
from collections import defaultdict
from time import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.logging import get_logger

_EXEMPT_PATHS = ("/healthz", "/readyz")

_TRUSTED_CIDRS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """按 IP 滑动窗口限流，默认每 IP 每分钟 60 次请求。"""

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int = 60,
        window_seconds: int = 60,
        max_tracked_clients: int = 5_000,
        prune_interval_seconds: int | None = None,
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_tracked_clients = max_tracked_clients
        self.prune_interval_seconds = prune_interval_seconds or max(window_seconds, 60)
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._last_seen: dict[str, float] = {}
        self._next_prune_at = 0.0

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        if any(path.startswith(prefix) for prefix in _EXEMPT_PATHS):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = time()
        cutoff = now - self.window_seconds

        if now >= self._next_prune_at:
            self._prune_expired(now)

        timestamps = self._requests.get(client_ip, [])
        active = [timestamp for timestamp in timestamps if timestamp > cutoff]
        if active:
            self._requests[client_ip] = active
            self._last_seen[client_ip] = active[-1]
        else:
            self._requests.pop(client_ip, None)
            self._last_seen.pop(client_ip, None)

        if len(active) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"status": "error", "message": "请求过于频繁，请稍后再试"},
            )

        if client_ip not in self._requests:
            self._ensure_capacity(required_slots=1)

        self._requests[client_ip].append(now)
        self._last_seen[client_ip] = now
        return await call_next(request)

    def _prune_expired(self, now: float) -> None:
        cutoff = now - self.window_seconds
        expired_clients: list[str] = []

        for client_ip, timestamps in list(self._requests.items()):
            active = [timestamp for timestamp in timestamps if timestamp > cutoff]
            if active:
                self._requests[client_ip] = active
                self._last_seen[client_ip] = active[-1]
            else:
                expired_clients.append(client_ip)

        for client_ip in expired_clients:
            self._requests.pop(client_ip, None)
            self._last_seen.pop(client_ip, None)

        self._next_prune_at = now + self.prune_interval_seconds

    def _ensure_capacity(self, required_slots: int = 1) -> None:
        overflow = len(self._requests) + required_slots - self.max_tracked_clients
        if overflow <= 0:
            return

        evicted_clients = sorted(self._last_seen.items(), key=lambda item: item[1])[:overflow]
        for client_ip, _ in evicted_clients:
            self._requests.pop(client_ip, None)
            self._last_seen.pop(client_ip, None)

        logger.warning(
            "rate_limit_client_cache_trimmed",
            evicted_count=len(evicted_clients),
            max_tracked_clients=self.max_tracked_clients,
        )

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        peer_ip = request.client.host if request.client else "unknown"
        try:
            addr = ipaddress.ip_address(peer_ip)
            is_trusted = any(addr in cidr for cidr in _TRUSTED_CIDRS)
        except ValueError:
            is_trusted = False

        if is_trusted:
            forwarded = request.headers.get("x-forwarded-for", "").strip()
            if forwarded:
                return forwarded.split(",", 1)[0].strip()
            real_ip = request.headers.get("x-real-ip", "").strip()
            if real_ip:
                return real_ip

        return peer_ip
