from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.engine.runner import ENGINE_RUN_ADVISORY_LOCK_KEY, _config_snapshot, run_engine


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

    def __call__(self) -> "_FakeSessionFactory":
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
    ) -> None:
        self.progress_calls.append(
            {"current_step": current_step, "step_detail": step_detail, "total_steps": total_steps}
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
        result = await run_engine(ctx)  # type: ignore[arg-type]

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
        patch("app.engine.runner.load_local_inventory", AsyncMock(return_value={"SKU-001": {"available": 0, "reserved": 0}})),
        patch("app.engine.runner.load_country_warehouses", AsyncMock(return_value={})),
        patch("app.engine.runner.load_zipcode_rules", AsyncMock(return_value=[])),
        patch("app.engine.runner.load_all_sku_country_orders", AsyncMock(return_value={})),
        patch("app.engine.runner._persist_suggestion", fake_persist),
    ):
        result = await run_engine(_FakeContext())  # type: ignore[arg-type]

    assert result == 123
    item = captured["items"][0]
    assert item["total_qty"] == 100
    assert item["purchase_qty"] == 235
    assert item["purchase_date"] == date.today() - timedelta(days=70)


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
        result = await run_engine(_FakeContext())  # type: ignore[arg-type]

    assert result is None
    persist.assert_not_awaited()


def test_engine_run_advisory_lock_key_is_stable() -> None:
    assert ENGINE_RUN_ADVISORY_LOCK_KEY == 7429001


@pytest.mark.asyncio
async def test_calc_engine_job_turns_off_toggle_on_success(monkeypatch) -> None:
    import app.engine.calc_engine_job as job_module

    config = _make_config(suggestion_generation_enabled=True)
    db = _FakeDb([_ScalarResult(config)])
    ctx = _FakeContext()
    ctx.payload = {"triggered_by": "manual"}

    monkeypatch.setattr(job_module, "run_engine", AsyncMock(return_value=123))
    monkeypatch.setattr(job_module, "async_session_factory", _FakeSessionFactory(db))

    await job_module.calc_engine_job(ctx)  # type: ignore[arg-type]

    assert config.suggestion_generation_enabled is False
    assert config.generation_toggle_updated_at is not None
    assert db.commits == 1


@pytest.mark.asyncio
async def test_calc_engine_job_keeps_toggle_on_failure(monkeypatch) -> None:
    import app.engine.calc_engine_job as job_module

    config = _make_config(suggestion_generation_enabled=True)
    db = _FakeDb([_ScalarResult(config)])
    ctx = _FakeContext()
    monkeypatch.setattr(job_module, "run_engine", AsyncMock(side_effect=RuntimeError("boom")))
    monkeypatch.setattr(job_module, "async_session_factory", _FakeSessionFactory(db))

    with pytest.raises(RuntimeError, match="boom"):
        await job_module.calc_engine_job(ctx)  # type: ignore[arg-type]

    assert config.suggestion_generation_enabled is True
    assert db.commits == 0
