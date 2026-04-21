from datetime import datetime
from typing import Any


class _FakeContext:
    def __init__(self) -> None:
        self.events: list[tuple[str | None, str | None, int | None]] = []

    async def progress(
        self,
        *,
        current_step: str | None = None,
        step_detail: str | None = None,
        total_steps: int | None = None,
    ) -> None:
        self.events.append((current_step, step_detail, total_steps))


class _FakeDb:
    pass


class _FakeSessionFactory:
    def __init__(self, dbs: list[_FakeDb]) -> None:
        self._dbs = list(dbs)

    def __call__(self) -> "_FakeSessionFactory":
        return self

    async def __aenter__(self) -> _FakeDb:
        return self._dbs.pop(0)

    async def __aexit__(self, *args: Any) -> None:
        return None


async def _async_set() -> set[str]:
    return set()


async def test_sync_order_list_skips_when_no_enabled_shops(monkeypatch) -> None:
    import app.sync.order_list as order_list_module

    started = datetime(2026, 4, 13, 9, 0, 0)
    factory = _FakeSessionFactory([_FakeDb(), _FakeDb()])
    success_calls: list[tuple[str, datetime]] = []

    async def _fake_mark_sync_running(_db, _job_name: str) -> datetime:
        return started

    async def _fake_compute_window(_db, _started: datetime) -> tuple[datetime, datetime]:
        return started, started

    async def _fake_resolve_shop_ids(_db) -> list[str]:
        return []

    async def _fake_mark_sync_success(_db, job_name: str, started_at: datetime) -> None:
        success_calls.append((job_name, started_at))

    async def _boom_list_orders(*_args, **_kwargs):
        raise AssertionError("list_orders should not be called when no shops are enabled")

    monkeypatch.setattr(order_list_module, "async_session_factory", factory)
    monkeypatch.setattr(order_list_module, "mark_sync_running", _fake_mark_sync_running)
    monkeypatch.setattr(order_list_module, "_compute_window", _fake_compute_window)
    monkeypatch.setattr(order_list_module, "_resolve_shop_ids", _fake_resolve_shop_ids)
    monkeypatch.setattr(order_list_module, "mark_sync_success", _fake_mark_sync_success)
    monkeypatch.setattr(order_list_module, "list_orders", _boom_list_orders)
    monkeypatch.setattr(order_list_module, "load_eu_countries", lambda _db: _async_set())

    ctx = _FakeContext()
    await order_list_module.sync_order_list_job(ctx)  # type: ignore[arg-type]

    assert success_calls == [(order_list_module.JOB_NAME, started)]
    assert ctx.events[0] == ("同步订单列表", None, 1)
    assert ctx.events[-1] == ("完成", "未启用任何店铺，跳过同步 0 / 0", None)
