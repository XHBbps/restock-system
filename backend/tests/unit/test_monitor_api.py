from datetime import datetime
from types import SimpleNamespace

import pytest

from app.api.monitor import _recent_call_out, get_api_calls


class _RowsResult:
    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return self._rows


class _ScalarResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one(self):
        return self._value


class _FakeDb:
    def __init__(self, responses) -> None:
        self._responses = list(responses)
        self.executed = []

    async def execute(self, stmt, *args, **kwargs):
        self.executed.append(stmt)
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_get_api_calls_returns_endpoint_overview_only() -> None:
    db = _FakeDb([_RowsResult([])])

    result = await get_api_calls(hours=24, db=db, _={})  # type: ignore[arg-type]

    assert result.endpoints == []
    assert len(db.executed) == 1


@pytest.mark.asyncio
async def test_get_api_calls_last_call_sql_has_no_embedded_python_import() -> None:
    """Regression for code review C-1.

    Ensure the "last call per endpoint" text() SQL does not accidentally contain
    a Python import statement inside the string literal. Triggers the `if rows:`
    branch by providing a non-empty first rows result.
    """
    db = _FakeDb([
        _RowsResult([("GET /foo", 10, 8, None)]),  # non-empty -> enters if-branch
        _RowsResult([]),                            # the buggy last_rows query
    ])

    await get_api_calls(hours=24, db=db, _={})  # type: ignore[arg-type]

    # The second executed statement is the text() last_rows SELECT DISTINCT ON.
    last_rows_stmt = db.executed[1]
    sql_text = str(last_rows_stmt).lower()
    assert "from typing import any" not in sql_text, (
        "SQL literal must not contain embedded Python import statement"
    )
    assert "select distinct on" in sql_text


def _call_row(**overrides):
    base = {
        "id": 1,
        "endpoint": "/api/shop/pageList.json",
        "called_at": datetime(2026, 5, 3, 12, 0, 0),
        "duration_ms": 100,
        "http_status": 200,
        "saihu_code": 40019,
        "saihu_msg": "rate limited",
        "error_type": "rate_limit",
        "retry_status": None,
        "auto_retry_attempts": 0,
        "next_retry_at": None,
        "resolved_at": None,
        "last_retry_error": None,
        "retry_source_log_id": None,
        "request_payload": {"pageNo": "1"},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_recent_call_retry_display_fields_cover_queue_states() -> None:
    cases = [
        ("queued", 0, None, "queued", "待自动重试", "0/5"),
        ("resolved", 2, None, "resolved", "已解决", "2/5"),
        ("permanent", 5, "still limited", "permanent", "永久失败", "5/5"),
        ("unsupported", 0, "no payload", "unsupported", "不支持自动重试", "0/5"),
    ]

    for status, attempts, error, display_status, display_text, attempt_text in cases:
        out = _recent_call_out(
            _call_row(
                retry_status=status,
                auto_retry_attempts=attempts,
                last_retry_error=error,
            )
        )

        assert out.retry_display_status == display_status
        assert out.retry_display_text == display_text
        assert out.retry_attempt_text == attempt_text


def test_recent_call_retry_display_fields_do_not_show_attempts_for_null_status() -> None:
    original = _recent_call_out(_call_row(retry_status=None, auto_retry_attempts=0))
    child = _recent_call_out(_call_row(retry_status=None, retry_source_log_id=88))

    assert original.retry_display_status == "not_queued"
    assert original.retry_display_text == "未入自动队列"
    assert original.retry_attempt_text == "-"
    assert child.retry_display_status == "retry_log"
    assert child.retry_display_text == "即时重试日志"
    assert child.retry_attempt_text == "-"
