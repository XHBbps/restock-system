"""Unit tests for order_detail fetch failure classification.

These tests lock in the rule that only SaihuBizError should be written to
order_detail_fetch_log as a permanent failure. Other Saihu exception subclasses
represent transient issues (client-level tenacity budget exhausted) and must
be allowed to retry on the next sync run.
"""

from app.core.exceptions import (
    SaihuAPIError,
    SaihuAuthExpired,
    SaihuBizError,
    SaihuNetworkError,
    SaihuRateLimited,
)
from app.sync.order_detail import _is_permanent_saihu_error


def test_saihu_biz_error_is_permanent() -> None:
    exc = SaihuBizError("订单不存在", code=40013)
    assert _is_permanent_saihu_error(exc) is True


def test_saihu_rate_limited_is_transient() -> None:
    exc = SaihuRateLimited("被限流", code=40019)
    assert _is_permanent_saihu_error(exc) is False


def test_saihu_network_error_is_transient() -> None:
    exc = SaihuNetworkError("连接超时")
    assert _is_permanent_saihu_error(exc) is False


def test_saihu_auth_expired_is_transient() -> None:
    exc = SaihuAuthExpired("token 失效", code=40001)
    assert _is_permanent_saihu_error(exc) is False


def test_bare_saihu_api_error_is_transient() -> None:
    # client.py raises `SaihuAPIError("unreachable", ...)` as a safety net.
    # Treat unclassified base-class errors as transient so they get another try.
    exc = SaihuAPIError("unreachable")
    assert _is_permanent_saihu_error(exc) is False


def test_generic_exception_is_transient() -> None:
    exc = RuntimeError("boom")
    assert _is_permanent_saihu_error(exc) is False
