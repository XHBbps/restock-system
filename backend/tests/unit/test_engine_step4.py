from unittest.mock import AsyncMock, patch

import pytest

from app.engine.context import EngineContext, LocalStock
from app.engine.sku_mapping import MappingComponent
from app.engine.step4_total import compute_total, load_local_inventory, step4_total
from app.engine.warehouse_scope import LOCAL_WAREHOUSE_TYPES


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeDb:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _RowsResult(self.rows)


def _has_type_param(params, values: tuple[int, ...]) -> bool:
    expected = sorted(values)
    return any(
        isinstance(value, (list, tuple)) and sorted(value) == expected
        for value in params.values()
    )


def test_step4_new_purchase_formula() -> None:
    ctx = EngineContext(
        country_qty={"sku1": {"US": 60, "EU": 40}},
        velocity={"sku1": {"US": 3, "EU": 2}},
        local_stock={"sku1": LocalStock(available=20, reserved=5)},
        buffer_days=30,
        safety_stock_days=15,
    )

    result = step4_total(ctx)

    assert result["sku1"] == 150


def test_step4_clamps_negative_purchase_qty_to_zero() -> None:
    """本地库存过剩时 raw = -50 应被 clamp 到 0（DB 侧也有 CheckConstraint 双保险）。"""
    ctx = EngineContext(
        country_qty={"sku1": {"US": 100}},
        velocity={"sku1": {"US": 0}},
        local_stock={"sku1": LocalStock(available=150, reserved=0)},
        buffer_days=30,
        safety_stock_days=15,
    )

    result = step4_total(ctx)

    assert result["sku1"] == 0


def test_step4_velocity_sum_includes_all_countries() -> None:
    ctx = EngineContext(
        country_qty={"sku1": {"US": 0}},
        velocity={"sku1": {"US": 3, "JP": 2}},
        local_stock={"sku1": LocalStock(available=0, reserved=0)},
        buffer_days=30,
        safety_stock_days=15,
    )

    result = step4_total(ctx)

    assert result["sku1"] == 75


def test_step4_buffer_days_does_not_affect_purchase_qty() -> None:
    without_buffer = compute_total(
        sku="sku1",
        country_qty_for_sku={"US": 100},
        velocity_for_sku={"US": 3, "JP": 2},
        local_stock_for_sku=LocalStock(available=20, reserved=5),
        buffer_days=0,
        safety_stock_days=15,
    )
    with_buffer = compute_total(
        sku="sku1",
        country_qty_for_sku={"US": 100},
        velocity_for_sku={"US": 3, "JP": 2},
        local_stock_for_sku=LocalStock(available=20, reserved=5),
        buffer_days=30,
        safety_stock_days=15,
    )

    assert without_buffer == 150
    assert with_buffer == without_buffer


@pytest.mark.asyncio
async def test_load_local_inventory_includes_default_and_domestic_warehouses() -> None:
    db = _FakeDb([("sku1", 7, 3)])

    with patch("app.engine.step4_total.load_active_mapping_rules", AsyncMock(return_value={})):
        result = await load_local_inventory(db, ["sku1"])

    assert result == {"sku1": LocalStock(available=7, reserved=3)}
    compiled_sql = str(db.statements[0])
    assert "warehouse.type IN" in compiled_sql
    assert _has_type_param(db.statements[0].compile().params, LOCAL_WAREHOUSE_TYPES)


@pytest.mark.asyncio
async def test_load_local_inventory_uses_default_and_domestic_component_stock() -> None:
    db = _FakeDb([])
    inventory_loader = AsyncMock(return_value={})

    with (
        patch(
            "app.engine.step4_total.load_active_mapping_rules",
            AsyncMock(
                return_value={"sku1": [[MappingComponent(inventory_sku="component", quantity=1)]]}
            ),
        ),
        patch("app.engine.step4_total.load_inventory_totals_by_warehouse", inventory_loader),
    ):
        await load_local_inventory(db, ["sku1"])

    assert inventory_loader.await_args.kwargs["warehouse_types"] == LOCAL_WAREHOUSE_TYPES
