"""每接口独立的 QPS 限流(aiolimiter)。

赛狐限制:大部分业务接口每秒最多 1 次请求;超过会触发 40019。
token 接口另有独立限制,但本模块只管理业务接口。
"""

from aiolimiter import AsyncLimiter

# 进程级 limiter 缓存:endpoint -> limiter
# P3-5: 有界性说明 — endpoint 集合固定(~7 个业务接口),
# 字典大小不会超过接口总数,不会内存泄漏。
_LIMITERS: dict[str, AsyncLimiter] = {}

# 默认每个 endpoint 1 次/秒
_DEFAULT_RATE = 1
_DEFAULT_PERIOD = 1.0

# 特定接口的 QPS 覆盖。当前没有遗留订单接口特例，保留映射用于后续扩展。
_ENDPOINT_RATE_OVERRIDES: dict[str, int] = {}


def get_endpoint_qps(endpoint: str) -> int:
    """Return the configured Saihu QPS for an endpoint."""

    return _ENDPOINT_RATE_OVERRIDES.get(endpoint, _DEFAULT_RATE)


def get_limiter(endpoint: str) -> AsyncLimiter:
    """获取(懒创建)某接口的 limiter。"""
    limiter = _LIMITERS.get(endpoint)
    if limiter is None:
        rate = get_endpoint_qps(endpoint)
        limiter = AsyncLimiter(rate, _DEFAULT_PERIOD)
        _LIMITERS[endpoint] = limiter
    return limiter
