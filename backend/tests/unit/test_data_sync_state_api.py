from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from app.api.data import list_sync_state


class _ScalarResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _RowsResult:
    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def scalars(self) -> _RowsResult:
        return self

    def all(self) -> list[Any]:
        return self._values


class _FakeSession:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.statements: list[Any] = []

    async def execute(self, statement: Any) -> Any:
        self.statements.append(statement)
        return self._responses.pop(0)


def _sync_row(
    job_name: str,
    *,
    last_run_at: datetime | None = None,
    last_success_at: datetime | None = None,
    last_status: str | None = None,
    last_error: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        job_name=job_name,
        last_run_at=last_run_at,
        last_success_at=last_success_at,
        last_status=last_status,
        last_error=last_error,
    )


def _task_row(
    job_name: str,
    status: str,
    *,
    id: int = 1,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    error_msg: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        job_name=job_name,
        status=status,
        created_at=created_at or datetime(2026, 5, 4, 1, 0, tzinfo=UTC),
        started_at=started_at,
        finished_at=finished_at,
        error_msg=error_msg,
    )


def _idle_background_responses() -> list[_ScalarResult]:
    return [_ScalarResult(None), _ScalarResult(None), _ScalarResult(None), _ScalarResult(None)]


@pytest.mark.asyncio
async def test_list_sync_state_keeps_sync_jobs_from_sync_state() -> None:
    run_at = datetime(2026, 5, 4, 3, 0, tzinfo=UTC)
    success_at = datetime(2026, 5, 4, 3, 1, tzinfo=UTC)
    db = _FakeSession(
        [
            _RowsResult(
                [
                    _sync_row(
                        "sync_shop",
                        last_run_at=run_at,
                        last_success_at=success_at,
                        last_status="success",
                    )
                ]
            ),
            *_idle_background_responses(),
        ]
    )

    result = await list_sync_state(db=db, _=None)  # type: ignore[arg-type]

    assert result[0].job_name == "sync_shop"
    assert result[0].last_run_at == run_at
    assert result[0].last_success_at == success_at
    assert result[0].last_status == "success"
    assert "sync_state.job_name IN" in str(db.statements[0])


@pytest.mark.asyncio
async def test_list_sync_state_adds_daily_archive_success_from_task_run() -> None:
    created_at = datetime(2026, 5, 4, 2, 0, tzinfo=UTC)
    started_at = datetime(2026, 5, 4, 2, 1, tzinfo=UTC)
    finished_at = datetime(2026, 5, 4, 2, 3, tzinfo=UTC)
    db = _FakeSession(
        [
            _RowsResult([]),
            _ScalarResult(
                _task_row(
                    "daily_archive",
                    "success",
                    created_at=created_at,
                    started_at=started_at,
                    finished_at=finished_at,
                )
            ),
            _ScalarResult(_task_row("daily_archive", "success", finished_at=finished_at)),
            _ScalarResult(None),
            _ScalarResult(None),
        ]
    )

    result = await list_sync_state(db=db, _=None)  # type: ignore[arg-type]

    daily_archive = next(item for item in result if item.job_name == "daily_archive")
    assert daily_archive.last_run_at == started_at
    assert daily_archive.last_success_at == finished_at
    assert daily_archive.last_status == "success"
    assert daily_archive.last_error is None


@pytest.mark.asyncio
async def test_list_sync_state_shows_error_only_when_latest_task_failed() -> None:
    failed_at = datetime(2026, 5, 4, 2, 5, tzinfo=UTC)
    success_at = datetime(2026, 5, 3, 2, 3, tzinfo=UTC)
    db = _FakeSession(
        [
            _RowsResult([]),
            _ScalarResult(
                _task_row(
                    "daily_archive",
                    "failed",
                    created_at=failed_at,
                    error_msg="archive failed",
                )
            ),
            _ScalarResult(_task_row("daily_archive", "success", finished_at=success_at)),
            _ScalarResult(None),
            _ScalarResult(None),
        ]
    )

    result = await list_sync_state(db=db, _=None)  # type: ignore[arg-type]

    daily_archive = next(item for item in result if item.job_name == "daily_archive")
    assert daily_archive.last_run_at == failed_at
    assert daily_archive.last_success_at == success_at
    assert daily_archive.last_status == "failed"
    assert daily_archive.last_error == "archive failed"


@pytest.mark.asyncio
async def test_list_sync_state_excludes_calc_engine_from_sync_log() -> None:
    db = _FakeSession(
        [
            _RowsResult([_sync_row("sync_shop"), _sync_row("calc_engine")]),
            *_idle_background_responses(),
        ]
    )

    result = await list_sync_state(db=db, _=None)  # type: ignore[arg-type]

    assert "calc_engine" not in {item.job_name for item in result}
    assert {"daily_archive", "retry_failed_api_calls"}.issubset({item.job_name for item in result})
