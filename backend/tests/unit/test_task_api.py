from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.api.task import (
    EnqueueRequest,
    cancel_task,
    create_task,
    get_task,
    list_tasks,
)
from app.core.exceptions import ConflictError, Forbidden
from app.core.permissions import HOME_REFRESH, RESTOCK_OPERATE, SYNC_OPERATE, SYNC_VIEW


class _ScalarResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one(self) -> Any:
        return self._value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _RowsResult:
    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def scalars(self) -> "_RowsResult":
        return self

    def all(self) -> list[Any]:
        return self._values


class _FakeDb:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.executed: list[Any] = []

    async def execute(self, stmt: Any) -> Any:
        self.executed.append(stmt)
        if not self._responses:
            return _ScalarResult(None)
        return self._responses.pop(0)


def _task_row(job_name: str, status: str = "pending") -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        job_name=job_name,
        dedupe_key=job_name,
        status=status,
        trigger_source="manual",
        priority=100,
        payload={},
        current_step=None,
        step_detail=None,
        total_steps=None,
        attempt_count=0,
        error_msg=None,
        result_summary=None,
        started_at=None,
        finished_at=None,
        created_at=datetime(2026, 4, 16, 10, 0, 0),
    )


@pytest.mark.asyncio
async def test_create_task_rejects_generic_push_saihu_enqueue() -> None:
    with pytest.raises(ConflictError, match="push_saihu"):
        await create_task(
            EnqueueRequest(job_name="push_saihu"),
            db=_FakeDb([]),  # type: ignore[arg-type]
            permissions=frozenset({RESTOCK_OPERATE}),
        )


@pytest.mark.asyncio
async def test_create_task_requires_job_specific_permission() -> None:
    with pytest.raises(Forbidden):
        await create_task(
            EnqueueRequest(job_name="sync_inventory"),
            db=_FakeDb([]),  # type: ignore[arg-type]
            permissions=frozenset({RESTOCK_OPERATE}),
        )


@pytest.mark.asyncio
async def test_create_task_rejects_calc_engine_generic_enqueue() -> None:
    with pytest.raises(ConflictError, match="calc_engine"):
        await create_task(
            EnqueueRequest(job_name="calc_engine"),
            db=_FakeDb([]),  # type: ignore[arg-type]
            permissions=frozenset({RESTOCK_OPERATE}),
        )


@pytest.mark.asyncio
async def test_create_task_allows_dashboard_refresh_permission(monkeypatch) -> None:
    enqueue_mock = AsyncMock(return_value=(88, False))
    monkeypatch.setattr("app.api.task.enqueue_task", enqueue_mock)

    result = await create_task(
        EnqueueRequest(job_name="refresh_dashboard_snapshot"),
        db=_FakeDb([]),  # type: ignore[arg-type]
        permissions=frozenset({HOME_REFRESH}),
    )

    assert result.task_id == 88
    enqueue_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_task_requires_job_specific_view_permission() -> None:
    with pytest.raises(Forbidden):
        await get_task(
            task_id=1,
            db=_FakeDb([_ScalarResult(_task_row("refresh_dashboard_snapshot"))]),  # type: ignore[arg-type]
            permissions=frozenset({"home:view"}),
        )


@pytest.mark.asyncio
async def test_list_tasks_filters_to_visible_jobs() -> None:
    db = _FakeDb([_ScalarResult(1), _RowsResult([_task_row("sync_inventory")])])

    result = await list_tasks(
        job_name=None,
        status=None,
        limit=20,
        db=db,  # type: ignore[arg-type]
        permissions=frozenset({SYNC_VIEW}),
    )

    assert result.total == 1
    assert [item.job_name for item in result.items] == ["sync_inventory"]


@pytest.mark.asyncio
async def test_cancel_task_requires_manage_permission() -> None:
    with pytest.raises(Forbidden):
        await cancel_task(
            task_id=1,
            db=_FakeDb([_ScalarResult(_task_row("sync_inventory"))]),  # type: ignore[arg-type]
            permissions=frozenset({SYNC_VIEW}),
        )


@pytest.mark.asyncio
async def test_cancel_task_allows_matching_manage_permission() -> None:
    db = _FakeDb([_ScalarResult(_task_row("sync_inventory"))])

    result = await cancel_task(
        task_id=1,
        db=db,  # type: ignore[arg-type]
        permissions=frozenset({SYNC_OPERATE}),
    )

    assert result == {"status": "cancelled"}
    assert len(db.executed) == 2
