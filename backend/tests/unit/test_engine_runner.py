"""Unit tests for app.engine.runner.

Strategy chosen:
  Option A + B hybrid.

  • _config_snapshot is a pure function — tested directly with a SimpleNamespace
    stub, no DB needed (Option A).
  • run_engine early-return path (no enabled SKUs) — tested by mocking
    async_session_factory so the DB returns an empty sku list (Option B).
  • _load_commodity_id_map — tested with a _FakeDb stub (Option B).

These three paths cover the most valuable/reachable lines without requiring
a live Postgres connection.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.engine.runner import (
    ENGINE_RUN_ADVISORY_LOCK_KEY,
    _config_snapshot,
    _load_commodity_id_map,
    run_engine,
)

# ---------------------------------------------------------------------------
# Shared fake DB plumbing (mirrors pattern in test_pushback_purchase.py)
# ---------------------------------------------------------------------------


class _ScalarResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one(self) -> Any:
        return self._value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> _ScalarsProxy:
        return _ScalarsProxy(self._value)

    def all(self) -> list[Any]:
        if self._value is None:
            return []
        if isinstance(self._value, list):
            return self._value
        return [self._value]


class _ScalarsProxy:
    def __init__(self, values: Any) -> None:
        self._values = values if isinstance(values, list) else [values]

    def all(self) -> list[Any]:
        return list(self._values)


class _FakeDb:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.commits = 0
        self.executed: list[Any] = []

    async def execute(self, stmt: Any, *args: Any, **kwargs: Any) -> Any:
        self.executed.append(stmt)
        if self._responses:
            return self._responses.pop(0)
        return _ScalarResult(None)

    async def commit(self) -> None:
        self.commits += 1


class _FakeSessionFactory:
    """Async context manager factory that yields a pre-configured _FakeDb."""

    def __init__(self, db: _FakeDb) -> None:
        self._db = db

    def __call__(self) -> _FakeSessionFactory:
        return self

    async def __aenter__(self) -> _FakeDb:
        return self._db

    async def __aexit__(self, *args: Any) -> None:
        return None


class _FakeContext:
    """Minimal JobContext stub."""

    def __init__(self) -> None:
        self.task_id = 1
        self.job_name = "run_engine"
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
        "restock_regions": [],
        "include_tax": "0",
        "default_purchase_warehouse_id": "WH-001",
        "shop_sync_mode": "all",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Option A: pure-function test for _config_snapshot
# ---------------------------------------------------------------------------


def test_config_snapshot_keys() -> None:
    """_config_snapshot returns the expected set of keys."""
    config = _make_config()
    snapshot = _config_snapshot(config)  # type: ignore[arg-type]

    assert snapshot["buffer_days"] == 30
    assert snapshot["target_days"] == 60
    assert snapshot["lead_time_days"] == 50
    assert snapshot["restock_regions"] == []
    assert snapshot["include_tax"] == "0"
    assert snapshot["default_purchase_warehouse_id"] == "WH-001"
    assert snapshot["shop_sync_mode"] == "all"
    assert "snapshot_at" in snapshot


def test_config_snapshot_overrides() -> None:
    """_config_snapshot reflects non-default values correctly."""
    config = _make_config(
        buffer_days=7,
        target_days=14,
        lead_time_days=21,
        restock_regions=["US", "GB"],
    )
    snapshot = _config_snapshot(config)  # type: ignore[arg-type]

    assert snapshot["buffer_days"] == 7
    assert snapshot["target_days"] == 14
    assert snapshot["lead_time_days"] == 21
    assert snapshot["restock_regions"] == ["US", "GB"]


# ---------------------------------------------------------------------------
# Option B: run_engine early-return when no SKUs are enabled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_engine_no_enabled_skus_returns_none() -> None:
    """run_engine returns None when no SKUs are enabled, without calling steps."""
    config = _make_config()

    # DB call sequence inside run_engine (no-SKU path):
    #   1. pg_advisory_xact_lock  -> None
    #   2. select GlobalConfig    -> config
    #   3. select enabled SKUs    -> [] (empty)
    db = _FakeDb(
        [
            None,                      # advisory lock
            _ScalarResult(config),     # GlobalConfig.scalar_one()
            _ScalarResult([]),         # enabled_skus.all() — empty list
        ]
    )
    factory = _FakeSessionFactory(db)
    ctx = _FakeContext()

    with patch("app.engine.runner.async_session_factory", factory):
        result = await run_engine(ctx)  # type: ignore[arg-type]

    assert result is None
    # Progress should have been called with the "完成" / skip message
    assert any(
        call.get("current_step") == "完成" for call in ctx.progress_calls
    )


@pytest.mark.asyncio
async def test_run_engine_forwards_restock_regions_to_step_loaders() -> None:
    config = _make_config(restock_regions=["US", "GB"])
    db = _FakeDb(
        [
            None,
            _ScalarResult(config),
            _ScalarResult([("SKU-001", None)]),
        ]
    )
    factory = _FakeSessionFactory(db)
    ctx = _FakeContext()

    mocked_run_step1 = AsyncMock(return_value={"SKU-001": {"US": 1.0}})
    mocked_run_step2 = AsyncMock(
        return_value=(
            {"SKU-001": {"US": 3.0}},
            {"SKU-001": {"US": {"available": 0, "reserved": 0, "in_transit": 0, "total": 0}}},
        )
    )
    mocked_load_local_inventory = AsyncMock(return_value={})
    mocked_load_country_warehouses = AsyncMock(return_value={"US": ["WH-US"]})
    mocked_load_zipcode_rules = AsyncMock(return_value=[])
    mocked_load_all_orders = AsyncMock(return_value={("SKU-001", "US"): []})
    mocked_load_commodity_ids = AsyncMock(return_value={"SKU-001": "CID-001"})
    mocked_persist = AsyncMock(return_value=123)

    with (
        patch("app.engine.runner.async_session_factory", factory),
        patch("app.engine.runner.run_step1", mocked_run_step1),
        patch("app.engine.runner.run_step2", mocked_run_step2),
        patch("app.engine.runner.load_local_inventory", mocked_load_local_inventory),
        patch("app.engine.runner.load_country_warehouses", mocked_load_country_warehouses),
        patch("app.engine.runner.load_zipcode_rules", mocked_load_zipcode_rules),
        patch("app.engine.runner.load_all_sku_country_orders", mocked_load_all_orders),
        patch("app.engine.runner._load_commodity_id_map", mocked_load_commodity_ids),
        patch("app.engine.runner.compute_country_qty", return_value={"SKU-001": {"US": 8}}),
        patch("app.engine.runner.compute_total", return_value=8),
        patch(
            "app.engine.runner.compute_urgency_for_sku",
            return_value=SimpleNamespace(urgent=False),
        ),
        patch("app.engine.runner._persist_suggestion", mocked_persist),
    ):
        result = await run_engine(ctx)  # type: ignore[arg-type]

    assert result == 123
    assert mocked_run_step1.await_args.kwargs["allowed_countries"] == {"US", "GB"}
    assert mocked_load_all_orders.await_args.kwargs["allowed_countries"] == {"US", "GB"}


def test_engine_run_advisory_lock_key_is_stable() -> None:
    """ENGINE_RUN_ADVISORY_LOCK_KEY is a fixed int (regression guard)."""
    assert ENGINE_RUN_ADVISORY_LOCK_KEY == 7429001


# ---------------------------------------------------------------------------
# Option B: _load_commodity_id_map with fake DB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_commodity_id_map_maps_sku_to_first_id() -> None:
    """_load_commodity_id_map returns correct sku->commodity_id mapping."""
    # rows returned by DB: list of (sku, commodity_id) tuples
    rows = [("SKU-A", "C001"), ("SKU-A", "C002"), ("SKU-B", "C010")]
    db = _FakeDb([_ScalarResult(rows)])
    # Patch .all() via the scalar result — our _ScalarResult.all() returns the list
    # but _load_commodity_id_map calls .all() on the execute result directly.
    # Provide a result object whose .all() returns the rows.
    db._responses = [SimpleNamespace(all=lambda: rows)]

    result = await _load_commodity_id_map(db, ["SKU-A", "SKU-B"])  # type: ignore[arg-type]

    # SKU-A should map to the first commodity_id encountered ("C001")
    assert result["SKU-A"] == "C001"
    assert result["SKU-B"] == "C010"


@pytest.mark.asyncio
async def test_load_commodity_id_map_ignores_inactive_or_unmatched_rows() -> None:
    rows = [
        ("SKU-A", "C999"),  # fake execute result only returns rows that survived SQL filters
        ("SKU-B", "C010"),
    ]
    db = _FakeDb([SimpleNamespace(all=lambda: rows)])

    result = await _load_commodity_id_map(db, ["SKU-A", "SKU-B"])  # type: ignore[arg-type]

    assert result["SKU-A"] == "C999"
    assert result["SKU-B"] == "C010"

    compiled_sql = str(db.executed[0]).lower()
    assert "product_listing.is_matched is true" in compiled_sql
    assert "product_listing.online_status = :online_status_1" in compiled_sql


@pytest.mark.asyncio
async def test_load_commodity_id_map_unknown_skus_map_to_none() -> None:
    """_load_commodity_id_map returns None for SKUs with no product listing."""
    db = _FakeDb([SimpleNamespace(all=lambda: [])])

    result = await _load_commodity_id_map(db, ["SKU-X", "SKU-Y"])  # type: ignore[arg-type]

    assert result["SKU-X"] is None
    assert result["SKU-Y"] is None


@pytest.mark.asyncio
async def test_load_commodity_id_map_falls_back_to_seller_sku() -> None:
    db = _FakeDb(
        [
            SimpleNamespace(all=lambda: []),
            SimpleNamespace(all=lambda: []),
            SimpleNamespace(all=lambda: []),
            SimpleNamespace(all=lambda: [("SKU-A", "CID-SELLER")]),
        ]
    )

    result = await _load_commodity_id_map(db, ["SKU-A"])  # type: ignore[arg-type]

    assert result["SKU-A"] == "CID-SELLER"
