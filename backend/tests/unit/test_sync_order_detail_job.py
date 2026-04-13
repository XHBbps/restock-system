from datetime import datetime
from typing import Any

import pytest

from app.core.exceptions import SaihuNetworkError


class _FakeContext:
    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.events: list[tuple[str | None, str | None, int | None]] = []
        self.payload = payload or {}

    async def progress(
        self,
        *,
        current_step: str | None = None,
        step_detail: str | None = None,
        total_steps: int | None = None,
    ) -> None:
        self.events.append((current_step, step_detail, total_steps))


class _FakeDb:
    async def commit(self) -> None:
        return None


class _FakeSessionFactory:
    def __init__(self, dbs: list[_FakeDb]) -> None:
        self._dbs = list(dbs)

    def __call__(self) -> "_FakeSessionFactory":
        return self

    async def __aenter__(self) -> _FakeDb:
        return self._dbs.pop(0)

    async def __aexit__(self, *args: Any) -> None:
        return None


@pytest.mark.asyncio
async def test_sync_order_detail_job_marks_failure_when_any_fetch_fails(monkeypatch) -> None:
    import app.sync.order_detail as order_detail_module

    started = datetime(2026, 4, 13, 10, 0, 0)
    factory = _FakeSessionFactory([_FakeDb(), _FakeDb(), _FakeDb()])
    failed_calls: list[tuple[str, str]] = []

    async def _fake_mark_sync_running(_db, _job_name: str) -> datetime:
        return started

    async def _fake_find_pending_orders(_db, _limit: int) -> list[tuple[str, str]]:
        return [("shop-1", "order-1")]

    async def _fake_get_order_detail(*, shop_id: str, amazon_order_id: str) -> dict[str, object]:
        raise SaihuNetworkError("timeout", endpoint="order_detail")

    async def _fake_mark_sync_failed(_db, job_name: str, error: str) -> None:
        failed_calls.append((job_name, error))

    async def _boom_mark_sync_success(_db, _job_name: str, _started: datetime) -> None:
        raise AssertionError("mark_sync_success should not be called when detail fetches fail")

    monkeypatch.setattr(order_detail_module, "async_session_factory", factory)
    monkeypatch.setattr(order_detail_module, "mark_sync_running", _fake_mark_sync_running)
    monkeypatch.setattr(order_detail_module, "_find_pending_orders", _fake_find_pending_orders)
    monkeypatch.setattr(order_detail_module, "get_order_detail", _fake_get_order_detail)
    monkeypatch.setattr(order_detail_module, "mark_sync_failed", _fake_mark_sync_failed)
    monkeypatch.setattr(order_detail_module, "mark_sync_success", _boom_mark_sync_success)

    ctx = _FakeContext()
    with pytest.raises(RuntimeError, match="订单详情同步存在失败"):
        await order_detail_module.sync_order_detail_job(ctx)  # type: ignore[arg-type]

    assert len(failed_calls) == 1
    assert failed_calls[0][0] == order_detail_module.JOB_NAME
    assert "failed=1" in failed_calls[0][1]


@pytest.mark.asyncio
async def test_refetch_order_detail_job_fetches_payload_targets(monkeypatch) -> None:
    import app.sync.order_detail as order_detail_module

    started = datetime(2026, 4, 13, 10, 0, 0)
    factory = _FakeSessionFactory([_FakeDb(), _FakeDb(), _FakeDb(), _FakeDb()])
    saved: list[tuple[str, str, dict[str, object]]] = []
    success_calls: list[tuple[str, datetime]] = []

    async def _fake_mark_sync_running(_db, _job_name: str) -> datetime:
        return started

    async def _fake_get_order_detail(*, shop_id: str, amazon_order_id: str) -> dict[str, object]:
        return {
            "marketplaceId": "ATVPDKIKX0DER",
            "postalCode": f"{shop_id}-{amazon_order_id}",
        }

    async def _fake_save_detail(_db, shop_id: str, amazon_order_id: str, detail: dict[str, object]) -> None:
        saved.append((shop_id, amazon_order_id, detail))

    async def _fake_mark_sync_success(_db, job_name: str, started_at: datetime) -> None:
        success_calls.append((job_name, started_at))

    monkeypatch.setattr(order_detail_module, "async_session_factory", factory)
    monkeypatch.setattr(order_detail_module, "mark_sync_running", _fake_mark_sync_running)
    monkeypatch.setattr(order_detail_module, "get_order_detail", _fake_get_order_detail)
    monkeypatch.setattr(order_detail_module, "_save_detail", _fake_save_detail)
    monkeypatch.setattr(order_detail_module, "mark_sync_success", _fake_mark_sync_success)

    ctx = _FakeContext(
        {
            "targets": [
                {"shop_id": "shop-1", "amazon_order_id": "order-1"},
                {"shop_id": "shop-2", "amazon_order_id": "order-2"},
            ]
        }
    )
    await order_detail_module.refetch_order_detail_job(ctx)  # type: ignore[arg-type]

    assert [(shop_id, amazon_order_id) for shop_id, amazon_order_id, _detail in saved] == [
        ("shop-1", "order-1"),
        ("shop-2", "order-2"),
    ]
    assert success_calls == [(order_detail_module.REFETCH_JOB_NAME, started)]
