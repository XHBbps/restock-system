from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from app.api.monitor import _can_retry
from app.core.exceptions import SaihuAPIError, ValidationFailed
from app.saihu.client import SaihuClient
from app.tasks.jobs.api_call_retry import (
    MAX_AUTO_RETRY_ATTEMPTS,
    _format_retry_error,
    _is_retryable_row,
    _payload_call_ids,
    busy_job_names_for_endpoint,
    retry_interval_seconds,
)


def test_retry_interval_uses_conservative_endpoint_qps() -> None:
    assert retry_interval_seconds("/api/shop/pageList.json") == 1.5
    assert retry_interval_seconds("/api/order/detailByOrderId.json") == 1.5


def test_busy_job_names_include_sync_all_for_package_orders() -> None:
    assert busy_job_names_for_endpoint("/api/packageShip/v1/getPackagePage.json") == (
        "sync_order_list",
        "sync_all",
    )
    assert busy_job_names_for_endpoint("/api/order/pageList.json") == ()
    assert busy_job_names_for_endpoint("/api/order/detailByOrderId.json") == ()


def test_payload_call_ids_filters_invalid_values() -> None:
    assert _payload_call_ids({}) is None
    assert _payload_call_ids({"call_ids": [1, "2", -3, 4]}) == [1, 4]
    assert _payload_call_ids({"call_ids": "bad"}) == []


def test_retryable_row_requires_40019_payload_and_non_terminal_status() -> None:
    row = SimpleNamespace(
        endpoint="/api/shop/pageList.json",
        saihu_code=40019,
        request_payload={"pageNo": "1"},
        retry_source_log_id=None,
        retry_status="queued",
        auto_retry_attempts=4,
    )
    assert _is_retryable_row(row) is True

    row.auto_retry_attempts = MAX_AUTO_RETRY_ATTEMPTS
    assert _is_retryable_row(row) is False
    row.auto_retry_attempts = 0
    row.retry_status = "permanent"
    assert _is_retryable_row(row) is False
    row.retry_status = "queued"
    row.request_payload = None
    assert _is_retryable_row(row) is False


def test_can_retry_requires_precise_original_40019_call() -> None:
    row = SimpleNamespace(
        saihu_code=40019,
        request_payload={"pageNo": "1"},
        retry_source_log_id=None,
        retry_status="queued",
        auto_retry_attempts=0,
    )
    assert _can_retry(row) is True

    row.retry_source_log_id = 10
    assert _can_retry(row) is False
    row.retry_source_log_id = None
    row.request_payload = None
    assert _can_retry(row) is False
    row.request_payload = {"pageNo": "1"}
    row.retry_status = "resolved"
    assert _can_retry(row) is False
    row.retry_status = "queued"
    row.saihu_code = 40001
    assert _can_retry(row) is False


def test_format_retry_error_includes_code_and_request_id() -> None:
    error = SaihuAPIError("failed", code=40002, request_id="req-1")
    assert _format_retry_error(error) == "failed code=40002 request_id=req-1"


@pytest.mark.asyncio
async def test_manual_retry_rejects_resolved_call() -> None:
    import app.api.monitor as monitor_module

    class _Result:
        def scalar_one_or_none(self):
            return SimpleNamespace(retry_status="resolved")

    class _Db:
        async def execute(self, _stmt):
            return _Result()

    with pytest.raises(ValidationFailed, match="已经解决"):
        await monitor_module.retry_call(1, db=_Db(), user=None, _=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_saihu_client_log_queues_final_40019_with_payload(monkeypatch) -> None:
    import app.saihu.client as client_module

    captured = {}

    class _Db:
        async def execute(self, stmt):
            captured.update(stmt.compile(dialect=postgresql.dialect()).params)

        async def commit(self):
            pass

    class _SessionFactory:
        async def __aenter__(self):
            return _Db()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(client_module, "async_session_factory", lambda: _SessionFactory())

    await SaihuClient()._log(
        "/api/shop/pageList.json",
        0.0,
        200,
        40019,
        "rate limited",
        "req-1",
        "rate_limit",
        3,
        {"pageNo": "1"},
        None,
        True,
    )

    assert captured["request_payload"] == {"pageNo": "1"}
    assert captured["retry_status"] == "queued"
    assert captured["retry_source_log_id"] is None
