"""Daily archive job 单元测试：INSERT inventory_snapshot_history + DELETE 过期。"""

from __future__ import annotations

from typing import Any

import pytest


class _Rowcount:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _FakeDb:
    def __init__(self, rowcounts: list[int]) -> None:
        self.statements: list[tuple[Any, Any]] = []
        self.commits = 0
        self._rowcounts = list(rowcounts)

    async def execute(self, stmt: Any, params: Any = None) -> _Rowcount:
        self.statements.append((stmt, params))
        return _Rowcount(self._rowcounts.pop(0))

    async def commit(self) -> None:
        self.commits += 1


class _FakeSessionFactory:
    def __init__(self, databases: list[_FakeDb]) -> None:
        self._queue = list(databases)

    def __call__(self) -> _FakeSessionCtx:
        return _FakeSessionCtx(self._queue.pop(0))


class _FakeSessionCtx:
    def __init__(self, db: _FakeDb) -> None:
        self._db = db

    async def __aenter__(self) -> _FakeDb:
        return self._db

    async def __aexit__(self, *args: Any) -> None:
        return None


class _FakeJobContext:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def progress(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


@pytest.mark.asyncio
async def test_daily_archive_job_inserts_then_cleans_old(monkeypatch) -> None:
    from app.tasks.jobs import daily_archive as job_module

    # 第 1 次 session：INSERT 追加到 history，返回 rowcount=42
    # 第 2 次 session：DELETE 过期 rows，返回 rowcount=10
    insert_db = _FakeDb(rowcounts=[42])
    delete_db = _FakeDb(rowcounts=[10])
    monkeypatch.setattr(
        job_module,
        "async_session_factory",
        _FakeSessionFactory([insert_db, delete_db]),
    )

    ctx = _FakeJobContext()
    await job_module.daily_archive_job(ctx)

    # INSERT 统计：一个 text() + params 包含 snapshot_date
    stmt_insert, params_insert = insert_db.statements[0]
    sql_insert = str(stmt_insert).lower()
    assert "insert into inventory_snapshot_history" in sql_insert
    assert "on conflict (commodity_sku, warehouse_id, snapshot_date)" in sql_insert
    assert "snapshot_date" in params_insert
    assert insert_db.commits == 1

    # DELETE 统计：一个 delete 语句带 cutoff
    stmt_delete, _ = delete_db.statements[0]
    sql_delete = str(stmt_delete).lower()
    assert "delete from inventory_snapshot_history" in sql_delete
    assert delete_db.commits == 1

    # 进度上报里应包含归档行数和清理行数
    step_details = " ".join(c.get("step_detail", "") for c in ctx.calls)
    assert "42" in step_details
    assert "10" in step_details


@pytest.mark.asyncio
async def test_daily_archive_job_handles_null_rowcount(monkeypatch) -> None:
    """SQLAlchemy 在某些情境下 rowcount=None，job 需要按 0 处理不抛异常。"""
    from app.tasks.jobs import daily_archive as job_module

    class _NullRowcountDb(_FakeDb):
        async def execute(self, stmt: Any, params: Any = None) -> _Rowcount:
            self.statements.append((stmt, params))
            return _Rowcount(None)  # type: ignore[arg-type]

    insert_db = _NullRowcountDb(rowcounts=[])
    delete_db = _NullRowcountDb(rowcounts=[])
    monkeypatch.setattr(
        job_module,
        "async_session_factory",
        _FakeSessionFactory([insert_db, delete_db]),
    )

    ctx = _FakeJobContext()
    await job_module.daily_archive_job(ctx)

    # 不应该抛异常，且两次 commit 都完成
    assert insert_db.commits == 1
    assert delete_db.commits == 1


@pytest.mark.asyncio
async def test_daily_archive_job_uses_retention_days_constant(monkeypatch) -> None:
    from app.tasks.jobs import daily_archive as job_module

    # 直接断言模块级常量存在，防止后续被误删
    assert isinstance(job_module.RETENTION_DAYS, int)
    assert job_module.RETENTION_DAYS > 0
