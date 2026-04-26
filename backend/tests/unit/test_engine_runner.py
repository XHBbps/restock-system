from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.engine.context import LocalStock
from app.engine.runner import (
    ENGINE_RUN_ADVISORY_LOCK_KEY,
    _config_snapshot,
    _persist_suggestion,
    run_engine,
)


class _ScalarResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one(self) -> Any:
        return self._value

    def all(self) -> list[Any]:
        if self._value is None:
            return []
        if isinstance(self._value, list):
            return self._value
        return [self._value]


class _FakeDb:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.commits = 0
        self.executed: list[Any] = []

    async def execute(self, stmt: Any, *_args: Any, **_kwargs: Any) -> Any:
        self.executed.append(stmt)
        if self._responses:
            return self._responses.pop(0)
        return _ScalarResult(None)

    async def commit(self) -> None:
        self.commits += 1


class _FakeSessionFactory:
    def __init__(self, db: _FakeDb) -> None:
        self._db = db

    def __call__(self) -> _FakeSessionFactory:
        return self

    async def __aenter__(self) -> _FakeDb:
        return self._db

    async def __aexit__(self, *args: Any) -> None:
        return None


class _FakeContext:
    def __init__(self) -> None:
        self.payload: dict[str, Any] = {}
        self.progress_calls: list[dict[str, Any]] = []

    async def progress(
        self,
        *,
        current_step: str | None = None,
        step_detail: str | None = None,
        total_steps: int | None = None,
        result_summary: str | None = None,
    ) -> None:
        self.progress_calls.append(
            {
                "current_step": current_step,
                "step_detail": step_detail,
                "total_steps": total_steps,
                "result_summary": result_summary,
            }
        )


def _make_config(**overrides: Any) -> SimpleNamespace:
    defaults = {
        "id": 1,
        "buffer_days": 30,
        "target_days": 60,
        "lead_time_days": 50,
        "safety_stock_days": 15,
        "restock_regions": [],
        "eu_countries": ["DE", "FR"],
        "shop_sync_mode": "all",
        "suggestion_generation_enabled": True,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_config_snapshot_keys() -> None:
    snapshot = _config_snapshot(_make_config())  # type: ignore[arg-type]

    assert snapshot["buffer_days"] == 30
    assert snapshot["target_days"] == 60
    assert snapshot["lead_time_days"] == 50
    assert snapshot["safety_stock_days"] == 15
    assert snapshot["restock_regions"] == []
    assert snapshot["eu_countries"] == ["DE", "FR"]
    assert "include_tax" not in snapshot
    assert "default_purchase_warehouse_id" not in snapshot


@pytest.mark.asyncio
async def test_run_engine_no_enabled_skus_returns_none() -> None:
    config = _make_config()
    db = _FakeDb([None, _ScalarResult(config), _ScalarResult([])])
    ctx = _FakeContext()

    with patch("app.engine.runner.async_session_factory", _FakeSessionFactory(db)):
        result = await run_engine(ctx, demand_date=date.today())  # type: ignore[arg-type]

    assert result is None
    assert any(call.get("current_step") == "完成" for call in ctx.progress_calls)


@pytest.mark.asyncio
async def test_run_engine_writes_purchase_fields_and_item_counts() -> None:
    config = _make_config(restock_regions=["US"])
    db = _FakeDb([None, _ScalarResult(config), _ScalarResult([("SKU-001", 50)])])
    captured: dict[str, Any] = {}

    async def fake_persist(_db: Any, **kwargs: Any) -> int:
        captured.update(kwargs)
        return 123

    with (
        patch("app.engine.runner.async_session_factory", _FakeSessionFactory(db)),
        patch("app.engine.runner.run_step1", AsyncMock(return_value={"SKU-001": {"US": 3.0}})),
        patch(
            "app.engine.runner.run_step2",
            AsyncMock(return_value=({"SKU-001": {"US": 30.0}}, {"SKU-001": {}})),
        ),
        patch("app.engine.runner.compute_country_qty", return_value={"SKU-001": {"US": 100}}),
        patch(
            "app.engine.runner.load_local_inventory",
            AsyncMock(return_value={"SKU-001": LocalStock(available=0, reserved=0)}),
        ),
        patch("app.engine.runner.load_country_warehouses", AsyncMock(return_value={})),
        patch("app.engine.runner.load_zipcode_rules", AsyncMock(return_value=[])),
        patch("app.engine.runner.load_all_sku_country_orders", AsyncMock(return_value={})),
        patch("app.engine.runner._persist_suggestion", fake_persist),
    ):
        demand_date = date.today()
        result = await run_engine(_FakeContext(), demand_date=demand_date)  # type: ignore[arg-type]

    assert result == 123
    item = captured["items"][0]
    assert item["total_qty"] == 100
    assert item["purchase_qty"] == 145
    assert item["restock_dates"] == {"US": (date.today() - timedelta(days=20)).isoformat()}


@pytest.mark.asyncio
async def test_run_engine_velocity_unaffected_by_restock_regions() -> None:
    """回归测试：restock_regions 白名单不应影响 Σvelocity 的取值。

    场景：SKU-001 在 US（白名单内）动销 3/天，在 JP（白名单外）动销 2/天。
    采购量公式：Σcountry_qty - local + Σvelocity × safety
             = 180        - 0     + 5       × 15     = 255
    country_qty 只保留 US（180），但 Σvelocity 必须覆盖所有国家（=5）。
    """
    config = _make_config(restock_regions=["US"])
    db = _FakeDb([None, _ScalarResult(config), _ScalarResult([("SKU-001", 50)])])
    captured: dict[str, Any] = {}

    async def fake_persist(_db: Any, **kwargs: Any) -> int:
        captured.update(kwargs)
        return 123

    step1_mock = AsyncMock(return_value={"SKU-001": {"US": 3.0, "JP": 2.0}})

    with (
        patch("app.engine.runner.async_session_factory", _FakeSessionFactory(db)),
        patch("app.engine.runner.run_step1", step1_mock),
        patch(
            "app.engine.runner.run_step2",
            AsyncMock(return_value=({"SKU-001": {"US": 30.0, "JP": 30.0}}, {"SKU-001": {}})),
        ),
        # 不 mock compute_country_qty，让真实 step3 基于 velocity 算出两国 qty
        patch(
            "app.engine.runner.load_local_inventory",
            AsyncMock(return_value={"SKU-001": LocalStock(available=0, reserved=0)}),
        ),
        patch("app.engine.runner.load_country_warehouses", AsyncMock(return_value={})),
        patch("app.engine.runner.load_zipcode_rules", AsyncMock(return_value=[])),
        patch("app.engine.runner.load_all_sku_country_orders", AsyncMock(return_value={})),
        patch("app.engine.runner._persist_suggestion", fake_persist),
    ):
        demand_date = date.today()
        result = await run_engine(_FakeContext(), demand_date=demand_date)  # type: ignore[arg-type]

    # step1 必须以全量 velocity 被调用（不传 allowed_countries）
    step1_mock.assert_awaited_once()
    call_kwargs = step1_mock.await_args.kwargs
    assert (
        call_kwargs.get("allowed_countries") is None
    ), f"run_step1 不应接收 allowed_countries 过滤 velocity，实际传了: {call_kwargs}"

    assert result == 123
    item = captured["items"][0]
    # country_qty 只保留白名单（US: 180），JP 被过滤
    assert item["country_breakdown"] == {"US": 180}
    assert item["total_qty"] == 180
    # purchase_qty = 180 - 0 + (3+2)*15 = 255
    # 关键：Σvelocity 含 JP 的 2/天，否则会少算 2*15=30，结果变 225
    assert item["purchase_qty"] == 255, "purchase_qty 应覆盖所有国家动销；若仅算白名单则为 225"
    assert item["restock_dates"] == {"US": (date.today() - timedelta(days=20)).isoformat()}


@pytest.mark.asyncio
async def test_run_engine_returns_none_when_all_items_empty() -> None:
    config = _make_config()
    db = _FakeDb([None, _ScalarResult(config), _ScalarResult([("SKU-001", None)])])
    persist = AsyncMock(return_value=123)

    with (
        patch("app.engine.runner.async_session_factory", _FakeSessionFactory(db)),
        patch("app.engine.runner.run_step1", AsyncMock(return_value={"SKU-001": {}})),
        patch("app.engine.runner.run_step2", AsyncMock(return_value=({"SKU-001": {}}, {}))),
        patch("app.engine.runner.compute_country_qty", return_value={"SKU-001": {}}),
        patch("app.engine.runner.load_local_inventory", AsyncMock(return_value={})),
        patch("app.engine.runner.load_country_warehouses", AsyncMock(return_value={})),
        patch("app.engine.runner.load_zipcode_rules", AsyncMock(return_value=[])),
        patch("app.engine.runner.load_all_sku_country_orders", AsyncMock(return_value={})),
        patch("app.engine.runner._persist_suggestion", persist),
    ):
        result = await run_engine(_FakeContext(), demand_date=date.today())  # type: ignore[arg-type]

    assert result is None
    persist.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_engine_keeps_safety_stock_purchase_only_item() -> None:
    config = _make_config(restock_regions=["US"])
    db = _FakeDb([None, _ScalarResult(config), _ScalarResult([("SKU-001", 50)])])
    captured: dict[str, Any] = {}

    async def fake_persist(_db: Any, **kwargs: Any) -> int:
        captured.update(kwargs)
        return 123

    with (
        patch("app.engine.runner.async_session_factory", _FakeSessionFactory(db)),
        patch("app.engine.runner.run_step1", AsyncMock(return_value={"SKU-001": {"US": 2.0}})),
        patch(
            "app.engine.runner.run_step2",
            AsyncMock(return_value=({"SKU-001": {"US": 120.0}}, {"SKU-001": {}})),
        ),
        patch("app.engine.runner.compute_country_qty", return_value={"SKU-001": {}}),
        patch(
            "app.engine.runner.load_local_inventory",
            AsyncMock(return_value={"SKU-001": LocalStock(available=0, reserved=0)}),
        ),
        patch("app.engine.runner.load_country_warehouses", AsyncMock(return_value={})),
        patch("app.engine.runner.load_zipcode_rules", AsyncMock(return_value=[])),
        patch("app.engine.runner.load_all_sku_country_orders", AsyncMock(return_value={})),
        patch("app.engine.runner._persist_suggestion", fake_persist),
    ):
        result = await run_engine(_FakeContext(), demand_date=date.today())  # type: ignore[arg-type]

    assert result == 123
    assert len(captured["items"]) == 1
    item = captured["items"][0]
    assert item["purchase_qty"] == 30
    assert item["total_qty"] == 0
    assert item["country_breakdown"] == {}
    assert item["warehouse_breakdown"] == {}
    assert item["allocation_snapshot"] == {}
    assert item["restock_dates"] == {}
    assert item["urgent"] is False


@pytest.mark.asyncio
async def test_run_engine_keeps_restock_and_purchase_only_items_together() -> None:
    config = _make_config(restock_regions=["US", "GB"])
    db = _FakeDb(
        [None, _ScalarResult(config), _ScalarResult([("SKU-RESTOCK", 50), ("SKU-SAFETY", 50)])]
    )
    captured: dict[str, Any] = {}

    async def fake_persist(_db: Any, **kwargs: Any) -> int:
        captured.update(kwargs)
        return 123

    with (
        patch("app.engine.runner.async_session_factory", _FakeSessionFactory(db)),
        patch(
            "app.engine.runner.run_step1",
            AsyncMock(
                return_value={
                    "SKU-RESTOCK": {"US": 3.0},
                    "SKU-SAFETY": {"GB": 2.0},
                }
            ),
        ),
        patch(
            "app.engine.runner.run_step2",
            AsyncMock(
                return_value=(
                    {
                        "SKU-RESTOCK": {"US": 30.0},
                        "SKU-SAFETY": {"GB": 120.0},
                    },
                    {"SKU-RESTOCK": {}, "SKU-SAFETY": {}},
                )
            ),
        ),
        patch(
            "app.engine.runner.compute_country_qty",
            return_value={"SKU-RESTOCK": {"US": 100}, "SKU-SAFETY": {}},
        ),
        patch(
            "app.engine.runner.load_local_inventory",
            AsyncMock(
                return_value={
                    "SKU-RESTOCK": LocalStock(available=0, reserved=0),
                    "SKU-SAFETY": LocalStock(available=0, reserved=0),
                }
            ),
        ),
        patch("app.engine.runner.load_country_warehouses", AsyncMock(return_value={})),
        patch("app.engine.runner.load_zipcode_rules", AsyncMock(return_value=[])),
        patch("app.engine.runner.load_all_sku_country_orders", AsyncMock(return_value={})),
        patch("app.engine.runner._persist_suggestion", fake_persist),
    ):
        demand_date = date.today()
        result = await run_engine(_FakeContext(), demand_date=demand_date)  # type: ignore[arg-type]

    assert result == 123
    items = {item["commodity_sku"]: item for item in captured["items"]}
    assert set(items) == {"SKU-RESTOCK", "SKU-SAFETY"}
    assert items["SKU-RESTOCK"]["total_qty"] == 100
    assert items["SKU-RESTOCK"]["purchase_qty"] == 145
    assert items["SKU-SAFETY"]["total_qty"] == 0
    assert items["SKU-SAFETY"]["purchase_qty"] == 30


def test_engine_run_advisory_lock_key_is_stable() -> None:
    assert ENGINE_RUN_ADVISORY_LOCK_KEY == 7429001


@pytest.mark.asyncio
async def test_run_engine_uses_restock_date_as_effective_target_days() -> None:
    config = _make_config(target_days=60)
    db = _FakeDb([None, _ScalarResult(config), _ScalarResult([("SKU-001", 50)])])

    with (
        patch("app.engine.runner.async_session_factory", _FakeSessionFactory(db)),
        patch("app.engine.runner.run_step1", AsyncMock(return_value={"SKU-001": {"US": 3.0}})),
        patch(
            "app.engine.runner.run_step2",
            AsyncMock(return_value=({"SKU-001": {"US": 30.0}}, {"SKU-001": {}})),
        ),
        patch(
            "app.engine.runner.compute_country_qty",
            return_value={"SKU-001": {"US": 100}},
        ) as compute_country_qty_mock,
        patch(
            "app.engine.runner.load_local_inventory",
            AsyncMock(return_value={"SKU-001": LocalStock(available=0, reserved=0)}),
        ),
        patch("app.engine.runner.load_country_warehouses", AsyncMock(return_value={})),
        patch("app.engine.runner.load_zipcode_rules", AsyncMock(return_value=[])),
        patch("app.engine.runner.load_all_sku_country_orders", AsyncMock(return_value={})),
        patch("app.engine.runner._persist_suggestion", AsyncMock(return_value=123)),
    ):
        await run_engine(
            _FakeContext(),
            demand_date=date.today() + timedelta(days=30),
        )  # type: ignore[arg-type]

    assert compute_country_qty_mock.call_args.args[2] == 90


@pytest.mark.asyncio
async def test_run_engine_keeps_countries_after_restock_date() -> None:
    config = _make_config()
    db = _FakeDb([None, _ScalarResult(config), _ScalarResult([("SKU-001", 50)])])
    captured: dict[str, Any] = {}

    async def fake_persist(_db: Any, **kwargs: Any) -> int:
        captured.update(kwargs)
        return 123

    with (
        patch("app.engine.runner.async_session_factory", _FakeSessionFactory(db)),
        patch(
            "app.engine.runner.run_step1",
            AsyncMock(return_value={"SKU-001": {"US": 1.0, "GB": 2.0}}),
        ),
        patch(
            "app.engine.runner.run_step2",
            AsyncMock(
                return_value=(
                    {"SKU-001": {"US": 10.0, "GB": 100.0}},
                    {"SKU-001": {}},
                )
            ),
        ),
        patch(
            "app.engine.runner.load_local_inventory",
            AsyncMock(return_value={"SKU-001": LocalStock(available=0, reserved=0)}),
        ),
        patch("app.engine.runner.load_country_warehouses", AsyncMock(return_value={})),
        patch("app.engine.runner.load_zipcode_rules", AsyncMock(return_value=[])),
        patch("app.engine.runner.load_all_sku_country_orders", AsyncMock(return_value={})),
        patch("app.engine.runner._persist_suggestion", fake_persist),
    ):
        result = await run_engine(
            _FakeContext(),
            demand_date=date.today(),
        )  # type: ignore[arg-type]

    assert result == 123
    item = captured["items"][0]
    assert item["country_breakdown"] == {"US": 60, "GB": 120}
    assert item["restock_dates"]["GB"] == (date.today() + timedelta(days=50)).isoformat()
    assert item["total_qty"] == 180
    assert item["purchase_qty"] == 225


@pytest.mark.asyncio
async def test_persist_suggestion_counts_procurement_and_restock_independently() -> None:
    db = _FakeDb([_ScalarResult(123)])
    items = [
        {
            "commodity_sku": "SKU-RESTOCK",
            "total_qty": 10,
            "country_breakdown": {"US": 10},
            "warehouse_breakdown": {},
            "allocation_snapshot": {},
            "velocity_snapshot": {},
            "sale_days_snapshot": {},
            "urgent": False,
            "purchase_qty": 20,
            "restock_dates": {"US": "2026-04-30"},
        },
        {
            "commodity_sku": "SKU-SAFETY",
            "total_qty": 0,
            "country_breakdown": {},
            "warehouse_breakdown": {},
            "allocation_snapshot": {},
            "velocity_snapshot": {},
            "sale_days_snapshot": {},
            "urgent": False,
            "purchase_qty": 30,
            "restock_dates": {},
        },
    ]

    suggestion_id = await _persist_suggestion(
        db,
        global_snapshot={},
        triggered_by="test",
        items=items,
    )

    assert suggestion_id == 123
    assert db.commits == 1
    params = db.executed[0].compile().params
    assert params["procurement_item_count"] == 2
    assert params["restock_item_count"] == 1


@pytest.mark.asyncio
async def test_calc_engine_job_turns_off_toggle_on_success(monkeypatch) -> None:
    import app.engine.calc_engine_job as job_module

    config = _make_config(suggestion_generation_enabled=True)
    db = _FakeDb([_ScalarResult(config)])
    ctx = _FakeContext()
    ctx.payload = {"triggered_by": "manual", "demand_date": "2026-04-30"}

    run_engine_mock = AsyncMock(return_value=123)
    monkeypatch.setattr(job_module, "run_engine", run_engine_mock)
    monkeypatch.setattr(job_module, "async_session_factory", _FakeSessionFactory(db))

    await job_module.calc_engine_job(ctx)  # type: ignore[arg-type]

    assert config.suggestion_generation_enabled is False
    assert config.generation_toggle_updated_at is not None
    assert db.commits == 1
    run_engine_mock.assert_awaited_once()
    assert run_engine_mock.await_args.kwargs["demand_date"] == date(2026, 4, 30)
    assert any(call.get("result_summary") for call in ctx.progress_calls)


@pytest.mark.asyncio
async def test_calc_engine_job_writes_no_suggestion_result_summary(monkeypatch) -> None:
    import app.engine.calc_engine_job as job_module

    ctx = _FakeContext()
    ctx.payload = {"triggered_by": "manual", "demand_date": "2026-04-30"}

    monkeypatch.setattr(job_module, "run_engine", AsyncMock(return_value=None))

    await job_module.calc_engine_job(ctx)  # type: ignore[arg-type]

    summary = next(call["result_summary"] for call in ctx.progress_calls if call["result_summary"])
    assert '"generated": false' in summary
    assert '"reason": "no_suggestion_needed"' in summary
    assert '"demand_date": "2026-04-30"' in summary


@pytest.mark.asyncio
async def test_calc_engine_job_keeps_toggle_on_failure(monkeypatch) -> None:
    import app.engine.calc_engine_job as job_module

    config = _make_config(suggestion_generation_enabled=True)
    db = _FakeDb([_ScalarResult(config)])
    ctx = _FakeContext()
    ctx.payload = {"triggered_by": "manual", "demand_date": "2026-04-30"}
    monkeypatch.setattr(job_module, "run_engine", AsyncMock(side_effect=RuntimeError("boom")))
    monkeypatch.setattr(job_module, "async_session_factory", _FakeSessionFactory(db))

    with pytest.raises(RuntimeError, match="boom"):
        await job_module.calc_engine_job(ctx)  # type: ignore[arg-type]

    assert config.suggestion_generation_enabled is True
    assert db.commits == 0
