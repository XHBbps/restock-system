"""业务异常层次。

分为两大类:
- SaihuAPIError 及其子类:赛狐 API 调用失败
- BusinessError 及其子类:系统内部业务逻辑异常
"""

from typing import Any


class BusinessError(Exception):
    """业务异常基类,所有内部抛出都应继承此类。"""

    status_code: int = 400

    def __init__(self, message: str, *, detail: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class NotFound(BusinessError):  # noqa: N818
    """资源未找到。"""

    status_code = 404


class Unauthorized(BusinessError):  # noqa: N818
    """未登录/token 无效。"""

    status_code = 401


class LoginLocked(BusinessError):  # noqa: N818
    """登录失败次数过多,账号被锁定。"""

    status_code = 423

    def __init__(self, message: str, locked_until: str) -> None:
        super().__init__(message, detail={"locked_until": locked_until})
        self.locked_until = locked_until


class ValidationFailed(BusinessError):  # noqa: N818
    """入参校验失败(非 Pydantic 层)。"""

    status_code = 400


class ConflictError(BusinessError):
    """状态冲突(如任务正在运行中)。"""

    status_code = 409


class PushBlockedError(BusinessError):
    """建议条目带有 push_blocker,不可推送。"""

    status_code = 400


# ==================== Saihu API Errors ====================


class SaihuAPIError(Exception):
    """赛狐 API 调用失败基类。"""

    def __init__(
        self,
        message: str,
        *,
        endpoint: str | None = None,
        code: int | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.endpoint = endpoint
        self.code = code
        self.request_id = request_id


class SaihuAuthExpired(SaihuAPIError):  # noqa: N818
    """token 失效(40001),应立即刷新并重试一次。"""


class SaihuRateLimited(SaihuAPIError):  # noqa: N818
    """请求被限流(40019),应退避后重试。"""


class SaihuBizError(SaihuAPIError):
    """赛狐业务错误(非限流/非鉴权),通常不应重试。"""


class SaihuNetworkError(SaihuAPIError):
    """网络层失败(超时 / 连接错误),可重试。"""
