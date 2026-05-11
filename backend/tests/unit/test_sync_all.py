from contextlib import asynccontextmanager

import pytest

from app.sync.all import sync_all_job
from app.sync.locks import SyncBusinessLockConflictError, sync_business_locks


class _FakeContext:
    def __init__(self) -> None:
        self.events: list[tuple[str | None, str | None, int | None]] = []
        self.payload: dict[str, object] = {}

    async def progress(
        self,
        *,
        current_step: str | None = None,
        step_detail: str | None = None,
        total_steps: int | None = None,
    ) -> None:
        self.events.append((current_step, step_detail, total_steps))


async def test_sync_all_runs_steps_in_order(monkeypatch) -> None:
    import app.sync.all as sync_all_module

    called: list[str] = []

    async def _job_one(_ctx) -> None:
        called.append("one")

    async def _job_two(_ctx) -> None:
        called.append("two")

    @asynccontextmanager
    async def _fake_locks(_job_names):
        yield ("sync_shop", "sync_warehouse")

    monkeypatch.setattr(
        sync_all_module,
        "SYNC_ALL_STEPS",
        [("step 1", _job_one), ("step 2", _job_two)],
    )
    monkeypatch.setattr(sync_all_module, "sync_business_locks", _fake_locks)

    ctx = _FakeContext()
    await sync_all_job(ctx)  # type: ignore[arg-type]

    assert called == ["one", "two"]
    assert ctx.events[0] == ("全量同步", "开始执行 2 个同步任务", 2)
    assert ctx.events[1] == ("1/2", "执行 step 1", 2)
    assert ctx.events[2] == ("2/2", "执行 step 2", 2)
    assert ctx.events[-1] == ("完成", "已串行完成 2 个同步任务", 2)


@pytest.mark.asyncio
async def test_sync_all_marks_child_locks_as_held(monkeypatch) -> None:
    import app.sync.all as sync_all_module

    seen_held: list[list[str]] = []

    async def _child(ctx) -> None:
        seen_held.append(list(ctx.payload["_held_sync_business_locks"]))

    @asynccontextmanager
    async def _fake_locks(_job_names):
        yield ("sync_inventory", "sync_order_list")

    monkeypatch.setattr(sync_all_module, "SYNC_ALL_STEPS", [("step", _child)])
    monkeypatch.setattr(sync_all_module, "sync_business_locks", _fake_locks)

    ctx = _FakeContext()
    await sync_all_job(ctx)  # type: ignore[arg-type]

    assert seen_held == [["sync_inventory", "sync_order_list"]]
    assert "_held_sync_business_locks" not in ctx.payload


@pytest.mark.asyncio
async def test_sync_business_locks_conflict_blocks_job(monkeypatch) -> None:
    import app.sync.locks as locks_module

    class _Result:
        def scalar_one(self):
            return False

    class _Db:
        async def execute(self, *_args, **_kwargs):
            return _Result()

    class _SessionFactory:
        async def __aenter__(self):
            return _Db()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(locks_module, "async_session_factory", lambda: _SessionFactory())

    with pytest.raises(SyncBusinessLockConflictError, match="sync_inventory"):
        async with sync_business_locks(["sync_inventory"]):
            pass
