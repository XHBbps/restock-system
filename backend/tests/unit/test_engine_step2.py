"""Unit tests for Step 2 sale_days."""

from unittest.mock import AsyncMock, patch

import pytest

from app.engine.context import InventoryStock
from app.engine.sku_mapping import MappingComponent, WarehouseStock
from app.engine.step2_sale_days import (
    compute_sale_days,
    load_in_transit,
    merge_inventory,
    run_step2,
)


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


@pytest.mark.asyncio
async def test_run_step2_keeps_known_zero_inventory_records_for_composite_skus() -> None:
    db = _FakeDb([])
    velocity = {"A": {"US": 1.0}}

    with (
        patch("app.engine.step2_sale_days.load_oversea_inventory", AsyncMock(return_value={})),
        patch("app.engine.step2_sale_days.load_in_transit", AsyncMock(return_value={})),
        patch(
            "app.engine.step2_sale_days.load_active_mapping_rules",
            AsyncMock(
                return_value={
                    "A": [
                        [
                            MappingComponent(inventory_sku="B", quantity=1),
                            MappingComponent(inventory_sku="C", quantity=1),
                        ]
                    ]
                }
            ),
        ),
        patch(
            "app.engine.step2_sale_days.load_inventory_totals_by_warehouse",
            AsyncMock(return_value={("B", "WH-US-1"): WarehouseStock(country="US", total=5)}),
        ),
        patch(
            "app.engine.step2_sale_days.load_in_transit_totals_by_warehouse",
            AsyncMock(return_value={}),
        ),
        patch(
            "app.engine.step2_sale_days.load_in_transit_totals_by_country",
            AsyncMock(return_value={}),
        ),
    ):
        sale_days, inventory = await run_step2(db, velocity, ["A"])

    assert inventory["A"]["US"].total == 0
    assert sale_days["A"]["US"] == 0.0


@pytest.mark.asyncio
async def test_run_step2_uses_country_level_transit_without_double_counting_warehouse_stock() -> None:
    db = _FakeDb([])
    velocity = {"A": {"US": 1.0}}

    with (
        patch("app.engine.step2_sale_days.load_oversea_inventory", AsyncMock(return_value={})),
        patch("app.engine.step2_sale_days.load_in_transit", AsyncMock(return_value={})),
        patch(
            "app.engine.step2_sale_days.load_active_mapping_rules",
            AsyncMock(
                return_value={
                    "A": [
                        [
                            MappingComponent(inventory_sku="B", quantity=1),
                            MappingComponent(inventory_sku="C", quantity=1),
                        ]
                    ]
                }
            ),
        ),
        patch(
            "app.engine.step2_sale_days.load_inventory_totals_by_warehouse",
            AsyncMock(
                return_value={
                    ("B", "WH-US-1"): WarehouseStock(country="US", total=5),
                    ("C", "WH-US-1"): WarehouseStock(country="US", total=5),
                }
            ),
        ),
        patch(
            "app.engine.step2_sale_days.load_in_transit_totals_by_warehouse",
            AsyncMock(return_value={}),
        ),
        patch(
            "app.engine.step2_sale_days.load_in_transit_totals_by_country",
            AsyncMock(return_value={("B", "US"): 5, ("C", "US"): 5}),
        ),
    ):
        sale_days, inventory = await run_step2(db, velocity, ["A"])

    assert inventory["A"]["US"].total == 10
    assert sale_days["A"]["US"] == 10.0


def test_merge_inventory_keeps_zero_transit_by_default() -> None:
    merged = merge_inventory(
        oversea={("sku-A", "US"): {"available": 10, "reserved": 2}},
        in_transit={},
    )

    assert merged["sku-A"]["US"] == InventoryStock(available=10, reserved=2, in_transit=0)


def test_compute_sale_days_uses_total_stock() -> None:
    sale_days = compute_sale_days(
        velocity={"sku-A": {"US": 5.0}},
        inventory={"sku-A": {"US": InventoryStock(available=10, reserved=5, in_transit=0)}},
    )

    assert sale_days["sku-A"]["US"] == 3.0


def test_compute_sale_days_skips_zero_or_negative_velocity() -> None:
    sale_days = compute_sale_days(
        velocity={"sku-A": {"US": 0.0, "CA": -1.0, "UK": 2.0}},
        inventory={
            "sku-A": {
                "US": InventoryStock(available=20, reserved=0, in_transit=0),
                "CA": InventoryStock(available=20, reserved=0, in_transit=0),
                "UK": InventoryStock(available=6, reserved=0, in_transit=0),
            }
        },
    )

    assert "US" not in sale_days.get("sku-A", {})
    assert "CA" not in sale_days.get("sku-A", {})
    assert sale_days["sku-A"]["UK"] == 3.0


def test_compute_sale_days_does_not_create_inventory_only_country() -> None:
    sale_days = compute_sale_days(
        velocity={"sku-A": {"US": 4.0}},
        inventory={
            "sku-A": {
                "US": InventoryStock(available=8, reserved=0, in_transit=0),
                "CA": InventoryStock(available=100, reserved=0, in_transit=0),
            }
        },
    )

    assert sale_days == {"sku-A": {"US": 2.0}}


def test_compute_sale_days_skips_missing_inventory_record() -> None:
    sale_days = compute_sale_days(
        velocity={"sku-A": {"US": 4.0}},
        inventory={},
    )

    assert sale_days == {}


def test_compute_sale_days_excludes_unknown_and_invalid_countries() -> None:
    sale_days = compute_sale_days(
        velocity={"sku-A": {"US": 4.0, "ZZ": 4.0, "": 4.0, "USA": 4.0}},
        inventory={
            "sku-A": {
                "US": InventoryStock(available=8, reserved=0, in_transit=0),
                "ZZ": InventoryStock(available=100, reserved=0, in_transit=0),
                "": InventoryStock(available=100, reserved=0, in_transit=0),
                "USA": InventoryStock(available=100, reserved=0, in_transit=0),
            }
        },
    )

    assert sale_days == {"sku-A": {"US": 2.0}}


@pytest.mark.asyncio
async def test_load_in_transit_reads_synced_tables_and_aggregates_goods() -> None:
    db = _FakeDb(
        [
            ("sku-A", "US", 12),
            ("sku-A", "JP", 5),
            ("sku-B", "US", 8),
        ]
    )

    result = await load_in_transit(db, ["sku-A", "sku-B"])

    assert result == {
        ("sku-A", "US"): 12,
        ("sku-A", "JP"): 5,
        ("sku-B", "US"): 8,
    }
    compiled_sql = str(db.statements[0])
    assert "in_transit_item" in compiled_sql
    assert "in_transit_record" in compiled_sql
    assert "suggestion_item" not in compiled_sql
