"""每接口独立的 1 QPS 限流（aiolimiter）。

赛狐限制：每个业务接口每秒最多 1 次请求；超过会触发 40019。
token 接口另有独立限制，但本模块只管理业务接口。
"""

from aiolimiter import AsyncLimiter

# 进程级 limiter 缓存：endpoint → limiter
_LIMITERS: dict[str, AsyncLimiter] = {}

# 默认每个 endpoint 1 次/秒
_DEFAULT_RATE = 1
_DEFAULT_PERIOD = 1.0


def get_limiter(endpoint: str) -> AsyncLimiter:
    """获取（懒创建）某接口的 limiter。"""
    limiter = _LIMITERS.get(endpoint)
    if limiter is None:
        limiter = AsyncLimiter(_DEFAULT_RATE, _DEFAULT_PERIOD)
        _LIMITERS[endpoint] = limiter
    return limiter
