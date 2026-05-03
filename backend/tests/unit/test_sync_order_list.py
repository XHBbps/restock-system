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
    def __init__(self) -> None:
        self.commits = 0
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> Any:
        self.statements.append(stmt)
        return None

    async def commit(self) -> None:
        self.commits += 1


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


async def test_sync_order_list_uses_package_endpoint_and_rolling_window(monkeypatch) -> None:
    import app.sync.order_list as order_list_module

    started = datetime(2026, 4, 29, 10, 0, 0)
    date_start = datetime(2025, 4, 29, 10, 0, 0)
    date_end = started
    factory = _FakeSessionFactory([_FakeDb(), _FakeDb(), _FakeDb(), _FakeDb()])
    success_calls: list[tuple[str, datetime, datetime | None]] = []
    package_calls: list[dict[str, Any]] = []

    async def _fake_mark_sync_running(_db, _job_name: str) -> datetime:
        return started

    def _fake_compute_window(_started: datetime) -> tuple[datetime, datetime]:
        return date_start, date_end

    async def _fake_resolve_shop_ids(_db) -> list[str]:
        return ["SHOP-1"]

    async def _fake_mark_sync_success(
        _db,
        job_name: str,
        started_at: datetime,
        success_at: datetime | None = None,
    ) -> None:
        success_calls.append((job_name, started_at, success_at))

    async def _fake_list_package_ship_orders(**kwargs):
        package_calls.append(kwargs)
        if False:
            yield {}

    monkeypatch.setattr(order_list_module, "async_session_factory", factory)
    monkeypatch.setattr(order_list_module, "mark_sync_running", _fake_mark_sync_running)
    monkeypatch.setattr(order_list_module, "_compute_window", _fake_compute_window)
    monkeypatch.setattr(order_list_module, "_resolve_shop_ids", _fake_resolve_shop_ids)
    monkeypatch.setattr(order_list_module, "mark_sync_success", _fake_mark_sync_success)
    monkeypatch.setattr(
        order_list_module,
        "list_package_ship_orders",
        _fake_list_package_ship_orders,
    )
    monkeypatch.setattr(order_list_module, "load_eu_countries", lambda _db: _async_set())

    ctx = _FakeContext()
    await order_list_module.sync_order_list_job(ctx)  # type: ignore[arg-type]

    assert success_calls == [(order_list_module.JOB_NAME, started, date_end)]
    assert package_calls[0]["purchase_date_start"] == "2025-04-29 10:00:00"
    assert package_calls[0]["purchase_date_end"] == "2026-04-29 10:00:00"
    assert package_calls[0]["shop_ids"] == ["SHOP-1"]
    assert package_calls[0]["page_size"] == 200


def test_subtract_calendar_months_clamps_month_end() -> None:
    from app.sync.order_list import _subtract_calendar_months

    assert _subtract_calendar_months(datetime(2026, 4, 29), 12) == datetime(2025, 4, 29)
    assert _subtract_calendar_months(datetime(2026, 8, 31), 12) == datetime(2025, 8, 31)
    assert _subtract_calendar_months(datetime(2024, 2, 29), 12) == datetime(2023, 2, 28)


async def test_sync_order_list_skips_when_no_enabled_shops_after_cleanup(monkeypatch) -> None:
    import app.sync.order_list as order_list_module

    started = datetime(2026, 4, 13, 9, 0, 0)
    factory = _FakeSessionFactory([_FakeDb(), _FakeDb(), _FakeDb()])
    success_calls: list[tuple[str, datetime, datetime | None]] = []

    async def _fake_mark_sync_running(_db, _job_name: str) -> datetime:
        return started

    def _fake_compute_window(_started: datetime) -> tuple[datetime, datetime]:
        return started, started

    async def _fake_resolve_shop_ids(_db) -> list[str]:
        return []

    async def _fake_mark_sync_success(
        _db,
        job_name: str,
        started_at: datetime,
        success_at: datetime | None = None,
    ) -> None:
        success_calls.append((job_name, started_at, success_at))

    async def _boom_list_package_ship_orders(*_args, **_kwargs):
        raise AssertionError("package endpoint should not be called when no shops are enabled")
        if False:
            yield {}

    monkeypatch.setattr(order_list_module, "async_session_factory", factory)
    monkeypatch.setattr(order_list_module, "mark_sync_running", _fake_mark_sync_running)
    monkeypatch.setattr(order_list_module, "_compute_window", _fake_compute_window)
    monkeypatch.setattr(order_list_module, "_resolve_shop_ids", _fake_resolve_shop_ids)
    monkeypatch.setattr(order_list_module, "mark_sync_success", _fake_mark_sync_success)
    monkeypatch.setattr(
        order_list_module,
        "list_package_ship_orders",
        _boom_list_package_ship_orders,
    )
    monkeypatch.setattr(order_list_module, "load_eu_countries", lambda _db: _async_set())

    ctx = _FakeContext()
    await order_list_module.sync_order_list_job(ctx)  # type: ignore[arg-type]

    assert success_calls == [(order_list_module.JOB_NAME, started, started)]
    assert ctx.events[0] == ("同步包裹订单列表", None, 1)
    assert ctx.events[-1][0] == "完成"
