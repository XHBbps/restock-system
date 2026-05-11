"""enqueue_task 递归深度限制测试。"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.schemas.sync import EngineRunIn
from app.tasks.queue import enqueue_task


class _FakeOriginalError(Exception):
    pass


def _make_dedupe_integrity_error():
    orig = _FakeOriginalError("uq_task_run_active_dedupe")
    exc = IntegrityError("", {}, orig)
    return exc


def _make_none_result():
    """模拟 SELECT 结果,scalar_one_or_none() 返回 None。"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    return result


@pytest.mark.asyncio
async def test_enqueue_task_recursive_retry_has_depth_limit():
    """P1-2: 递归重试不应无限循环。"""
    db = AsyncMock()
    db.rollback = AsyncMock()

    call_count = 0

    async def execute_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # 奇数次调用 = INSERT -> 抛冲突错误
        # 偶数次调用 = SELECT existing_id -> 返回 None(模拟活跃记录消失)
        if call_count % 2 == 1:
            raise _make_dedupe_integrity_error()
        return _make_none_result()

    db.execute = execute_side_effect

    with pytest.raises(RuntimeError, match="去重竞态重试耗尽"):
        await enqueue_task(
            db,
            job_name="test_job",
            trigger_source="manual",
            dedupe_key="test_key",
        )


@pytest.mark.asyncio
async def test_calc_engine_enqueue_dedupe_key_includes_demand_date(monkeypatch):
    import app.api.sync as sync_api

    captured = {}

    async def _fake_enqueue_task(_db, **kwargs):
        captured.update(kwargs)
        return 123, False

    monkeypatch.setattr(sync_api, "enqueue_task", _fake_enqueue_task)

    result = await sync_api.run_engine_now(
        EngineRunIn(demand_date="2099-05-20"),
        db=object(),  # type: ignore[arg-type]
        user=None,  # type: ignore[arg-type]
        _=None,
    )

    assert result == {"task_id": 123, "existing": False}
    assert captured["job_name"] == "calc_engine"
    assert captured["dedupe_key"] == "calc_engine:2099-05-20"
    assert captured["payload"]["demand_date"] == "2099-05-20"
