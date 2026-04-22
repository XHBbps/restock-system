"""Reaper 单元测试：lease 过期任务标记为 failed 的 SQL 行为 + 状态机。"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest


class _RowsResult:
    def __init__(self, ids: list[int]) -> None:
        self._rows = [(i,) for i in ids]

    def all(self) -> list[tuple[int]]:
        return self._rows


class _FakeDb:
    def __init__(self, reap_ids: list[int]) -> None:
        self.statements: list[Any] = []
        self.commits = 0
        self._reap_ids = reap_ids

    async def execute(self, stmt: Any) -> _RowsResult:
        self.statements.append(stmt)
        return _RowsResult(self._reap_ids)

    async def commit(self) -> None:
        self.commits += 1


class _FakeSessionFactory:
    def __init__(self, db: _FakeDb) -> None:
        self._db = db

    def __call__(self) -> "_FakeSessionCtx":
        return _FakeSessionCtx(self._db)


class _FakeSessionCtx:
    def __init__(self, db: _FakeDb) -> None:
        self._db = db

    async def __aenter__(self) -> _FakeDb:
        return self._db

    async def __aexit__(self, *args: Any) -> None:
        return None


@pytest.mark.asyncio
async def test_reaper_reap_once_collects_zombies(monkeypatch) -> None:
    from app.tasks import reaper as reaper_module

    db = _FakeDb(reap_ids=[11, 22, 33])
    monkeypatch.setattr(reaper_module, "async_session_factory", _FakeSessionFactory(db))

    r = reaper_module.Reaper()
    await r._reap_once()

    assert db.commits == 1
    sql = str(db.statements[0]).lower()
    assert "update task_run" in sql
    assert "status = 'failed'" in sql
    assert "lease_expires_at < now()" in sql
    assert "returning id" in sql


@pytest.mark.asyncio
async def test_reaper_reap_once_no_zombies_still_commits(monkeypatch) -> None:
    from app.tasks import reaper as reaper_module

    db = _FakeDb(reap_ids=[])
    monkeypatch.setattr(reaper_module, "async_session_factory", _FakeSessionFactory(db))

    r = reaper_module.Reaper()
    await r._reap_once()

    # 没 zombies 也走一次 commit（空 UPDATE 也应提交事务保证干净）
    assert db.commits == 1


@pytest.mark.asyncio
async def test_reaper_start_stop_lifecycle(monkeypatch) -> None:
    """start() 启动循环、stop() 优雅退出，不能有残留 task。"""
    from app.tasks import reaper as reaper_module

    db = _FakeDb(reap_ids=[])
    monkeypatch.setattr(reaper_module, "async_session_factory", _FakeSessionFactory(db))

    r = reaper_module.Reaper()
    assert r.running is False
    r.start()
    assert r.running is True
    # 给循环跑一次的机会
    await asyncio.sleep(0.05)
    await r.stop()
    assert r.running is False
    assert db.commits >= 1  # 至少跑过一次 reap_once


@pytest.mark.asyncio
async def test_reaper_start_idempotent(monkeypatch) -> None:
    """重复 start() 不应产生多个后台 task。"""
    from app.tasks import reaper as reaper_module

    db = _FakeDb(reap_ids=[])
    monkeypatch.setattr(reaper_module, "async_session_factory", _FakeSessionFactory(db))

    r = reaper_module.Reaper()
    r.start()
    first_task = r._task
    r.start()  # 第二次 start 应沿用同一个 task
    assert r._task is first_task
    await r.stop()


def test_get_reaper_singleton() -> None:
    from app.tasks.reaper import get_reaper

    a = get_reaper()
    b = get_reaper()
    assert a is b
