"""Retention job 单元测试：task_run / inventory_history / exports 三连。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.timezone import BEIJING
from app.tasks.jobs.retention import (
    purge_exports,
    purge_inventory_history,
    purge_task_run,
)


class _RowcountResult:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _ScalarsResult:
    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return list(self._values)


class _TupleRowsResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeDb:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.executed: list[Any] = []

    async def execute(self, stmt):
        self.executed.append(stmt)
        return self._responses.pop(0)


# --------- purge_task_run ---------

@pytest.mark.asyncio
async def test_purge_task_run_returns_zero_when_days_zero() -> None:
    db = _FakeDb([])
    result = await purge_task_run(db, days=0)
    assert result == 0
    assert db.executed == []


@pytest.mark.asyncio
async def test_purge_task_run_returns_deleted_rowcount() -> None:
    db = _FakeDb([_RowcountResult(7)])
    result = await purge_task_run(db, days=90)
    assert result == 7
    assert len(db.executed) == 1


@pytest.mark.asyncio
async def test_purge_task_run_none_rowcount_returns_zero() -> None:
    db = _FakeDb([_RowcountResult(None)])  # type: ignore[arg-type]
    result = await purge_task_run(db, days=90)
    assert result == 0


# --------- purge_inventory_history ---------

@pytest.mark.asyncio
async def test_purge_inventory_history_returns_zero_when_days_zero() -> None:
    db = _FakeDb([])
    result = await purge_inventory_history(db, days=0)
    assert result == 0
    assert db.executed == []


@pytest.mark.asyncio
async def test_purge_inventory_history_returns_deleted_rowcount() -> None:
    db = _FakeDb([_RowcountResult(12)])
    result = await purge_inventory_history(db, days=180)
    assert result == 12


# --------- purge_exports ---------

@pytest.mark.asyncio
async def test_purge_exports_returns_zero_when_days_zero(tmp_path: Path) -> None:
    db = _FakeDb([])
    result = await purge_exports(db, days=0, storage_root=tmp_path)
    assert result == 0


@pytest.mark.asyncio
async def test_purge_exports_returns_zero_when_nothing_to_purge(tmp_path: Path) -> None:
    db = _FakeDb([_ScalarsResult([])])  # 没有可清的 log
    result = await purge_exports(db, days=60, storage_root=tmp_path)
    assert result == 0


@pytest.mark.asyncio
async def test_purge_exports_deletes_file_and_marks_log(tmp_path: Path) -> None:
    # 构造 2 个 snapshot，各一个 Excel 文件
    snap_a_file = tmp_path / "2026" / "01" / "snap_a.xlsx"
    snap_a_file.parent.mkdir(parents=True)
    snap_a_file.write_bytes(b"fake xlsx A")
    snap_b_file = tmp_path / "2026" / "01" / "snap_b.xlsx"
    snap_b_file.write_bytes(b"fake xlsx B")
    assert snap_a_file.exists()
    assert snap_b_file.exists()

    db = _FakeDb(
        [
            _ScalarsResult([101, 102]),  # distinct snapshot_ids 待清理
            _TupleRowsResult(
                [
                    (101, "2026/01/snap_a.xlsx"),
                    (102, "2026/01/snap_b.xlsx"),
                ]
            ),  # snapshot.file_path 查询
            _RowcountResult(1),  # update log 101
            _RowcountResult(1),  # update log 102
        ]
    )

    purged = await purge_exports(db, days=60, storage_root=tmp_path)

    assert purged == 2
    assert not snap_a_file.exists()
    assert not snap_b_file.exists()


@pytest.mark.asyncio
async def test_purge_exports_handles_missing_file(tmp_path: Path) -> None:
    """文件已不在磁盘（比如上次 purge 跑了一半崩），应仍标记 log 避免反复重试。"""
    db = _FakeDb(
        [
            _ScalarsResult([200]),
            _TupleRowsResult([(200, "2026/02/missing.xlsx")]),
            _RowcountResult(1),
        ]
    )

    purged = await purge_exports(db, days=60, storage_root=tmp_path)

    # 文件不存在但仍把 log 标记为已清理（防止每天 04:00 重复扫到）
    assert purged == 1


@pytest.mark.asyncio
async def test_purge_exports_rejects_path_traversal(tmp_path: Path) -> None:
    """file_path 若指向 storage_root 外（例如被篡改），应拒绝删除并跳过。"""
    # 构造一个 storage_root 外的文件
    escape_root = tmp_path / "escape"
    escape_root.mkdir()
    evil_file = escape_root / "evil.xlsx"
    evil_file.write_bytes(b"important")
    storage_root = tmp_path / "exports"
    storage_root.mkdir()

    db = _FakeDb(
        [
            _ScalarsResult([300]),
            _TupleRowsResult([(300, "../escape/evil.xlsx")]),
            # 注意：traversal 被跳过，不进入 update 分支，所以只有 2 个响应
        ]
    )

    purged = await purge_exports(db, days=60, storage_root=storage_root)

    assert purged == 0
    assert evil_file.exists()


@pytest.mark.asyncio
async def test_purge_exports_skips_snapshot_with_null_file_path(tmp_path: Path) -> None:
    """snapshot.file_path IS NULL（生成失败的快照），仍应标记 log。"""
    db = _FakeDb(
        [
            _ScalarsResult([400]),
            _TupleRowsResult([(400, None)]),
            _RowcountResult(1),
        ]
    )

    purged = await purge_exports(db, days=60, storage_root=tmp_path)

    assert purged == 1


# 时区 sanity
def test_now_beijing_is_tz_aware() -> None:
    # 保证 cutoff 计算不会因 naive datetime 出 comparison 错误
    ts = datetime.now(tz=BEIJING)
    assert ts.tzinfo is not None
    # 与 UTC 偏移 8 小时
    assert ts.utcoffset() == timedelta(hours=8)
    _ = timezone  # 消除未使用导入告警
    _ = SimpleNamespace  # 同上


# --------- purge_stuck_generating ---------

@pytest.mark.asyncio
async def test_purge_stuck_generating_returns_zero_when_hours_zero() -> None:
    from app.tasks.jobs.retention import purge_stuck_generating

    db = _FakeDb([])
    result = await purge_stuck_generating(db, hours=0)
    assert result == 0
    assert db.executed == []


@pytest.mark.asyncio
async def test_purge_stuck_generating_marks_rows_failed() -> None:
    from app.tasks.jobs.retention import purge_stuck_generating

    db = _FakeDb([_RowcountResult(3)])
    result = await purge_stuck_generating(db, hours=1)
    assert result == 3
    # 只执行了 1 条 UPDATE 语句
    assert len(db.executed) == 1
    # SQL 含 generation_status='generating' + 时间阈值（exported_at < cutoff）
    compiled = str(db.executed[0]).lower()
    assert "generation_status" in compiled
    assert "exported_at" in compiled, (
        "WHERE 子句丢失 exported_at 时间阈值 → 会标所有 generating 而不管年龄"
    )


@pytest.mark.asyncio
async def test_purge_stuck_generating_handles_null_rowcount() -> None:
    from app.tasks.jobs.retention import purge_stuck_generating

    db = _FakeDb([_RowcountResult(None)])  # type: ignore[arg-type]
    result = await purge_stuck_generating(db, hours=1)
    assert result == 0
