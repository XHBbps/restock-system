"""Unit tests for Step 2 sale_days."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.engine.context import InventoryStock
from app.engine.sku_mapping import MappingComponent, WarehouseStock
from app.engine.step2_sale_days import (
    compute_sale_days,
    load_in_transit,
    load_third_party_component_inventory_by_warehouse,
    load_third_party_inventory,
    merge_inventory,
    run_step2,
)
from app.engine.warehouse_scope import LOCAL_WAREHOUSE_TYPES


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeDb:
    def __init__(self, rows, *, config=None):
        self.rows = rows
        self.config = config
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _RowsResult(self.rows)

    async def get(self, _model, _pk):
        return self.config


def _compiled_params(stmt):
    return stmt.compile().params


def _has_type_param(params, values: tuple[int, ...]) -> bool:
    expected = sorted(values)
    return any(
        isinstance(value, (list, tuple)) and sorted(value) == expected for value in params.values()
    )


@pytest.mark.asyncio
async def test_load_third_party_inventory_reads_only_country_warehouses() -> None:
    db = _FakeDb(
        [
            ("sku-A", "US", 7, 2),
            ("sku-A", None, 100, 0),
            ("sku-B", "ZZ", 100, 0),
        ]
    )

    result = await load_third_party_inventory(db, ["sku-A", "sku-B"])

    assert result == {("sku-A", "US"): {"available": 7, "reserved": 2}}
    compiled_sql = str(db.statements[0])
    assert "third_party_inventory_current" in compiled_sql
    assert "third_party_warehouse.country IS NOT NULL" in compiled_sql


@pytest.mark.asyncio
async def test_load_third_party_inventory_maps_eu_countries_before_aggregation() -> None:
    db = _FakeDb(
        [
            ("sku-A", "DE", 7, 2),
            ("sku-A", "FR", 3, 1),
            ("sku-A", "US", 5, 0),
            ("sku-B", "", 100, 0),
            ("sku-B", "ZZ", 100, 0),
            ("sku-B", "USA", 100, 0),
        ]
    )

    result = await load_third_party_inventory(
        db,
        ["sku-A", "sku-B"],
        eu_countries={"DE", "FR"},
    )

    assert result == {
        ("sku-A", "EU"): {"available": 10, "reserved": 3},
        ("sku-A", "US"): {"available": 5, "reserved": 0},
    }


@pytest.mark.asyncio
async def test_load_third_party_component_inventory_uses_prefixed_warehouse_keys() -> None:
    db = _FakeDb(
        [
            ("component-A", 1, "US", 7),
            ("component-A-alt", 1, "US", 3),
            ("component-B", 2, None, 100),
            ("component-C", 3, "ZZ", 100),
        ]
    )

    result = await load_third_party_component_inventory_by_warehouse(
        db,
        ["component-A", "component-A-alt", "component-B", "component-C"],
        sku_to_group_key={"component-A-alt": "component-A"},
    )

    assert result == {("component-A", "third_party:1"): WarehouseStock(country="US", total=10)}
    compiled_sql = str(db.statements[0])
    assert "third_party_inventory_current" in compiled_sql
    assert "third_party_warehouse.country IS NOT NULL" in compiled_sql


@pytest.mark.asyncio
async def test_load_third_party_component_inventory_maps_eu_country_by_warehouse() -> None:
    db = _FakeDb(
        [
            ("component-A", 1, "DE", 7),
            ("component-A-alt", 1, "DE", 3),
            ("component-B", 2, "US", 5),
            ("component-C", 3, "ZZ", 100),
        ]
    )

    result = await load_third_party_component_inventory_by_warehouse(
        db,
        ["component-A", "component-A-alt", "component-B", "component-C"],
        sku_to_group_key={"component-A-alt": "component-A"},
        eu_countries={"DE", "FR"},
    )

    assert result == {
        ("component-A", "third_party:1"): WarehouseStock(country="EU", total=10),
        ("component-B", "third_party:2"): WarehouseStock(country="US", total=5),
    }


@pytest.mark.asyncio
async def test_run_step2_uses_third_party_inventory_as_overseas_stock() -> None:
    db = _FakeDb([])
    velocity = {"sku-A": {"US": 3.0}}

    with (
        patch(
            "app.engine.step2_sale_days.load_third_party_inventory",
            AsyncMock(return_value={("sku-A", "US"): {"available": 7, "reserved": 2}}),
        ),
        patch("app.engine.step2_sale_days.load_in_transit", AsyncMock(return_value={})),
        patch("app.engine.step2_sale_days.load_active_mapping_rules", AsyncMock(return_value={})),
    ):
        sale_days, inventory = await run_step2(db, velocity, ["sku-A"])

    assert inventory["sku-A"]["US"] == InventoryStock(available=7, reserved=2, in_transit=0)
    assert sale_days["sku-A"]["US"] == 3.0


@pytest.mark.asyncio
async def test_run_step2_passes_eu_countries_to_third_party_loaders() -> None:
    db = _FakeDb([], config=SimpleNamespace(eu_countries=["DE", "FR"]))
    velocity = {"sku-A": {"EU": 3.0}}
    direct_loader = AsyncMock(return_value={("sku-A", "EU"): {"available": 7, "reserved": 2}})

    with (
        patch("app.engine.step2_sale_days.load_third_party_inventory", direct_loader),
        patch("app.engine.step2_sale_days.load_in_transit", AsyncMock(return_value={})),
        patch("app.engine.step2_sale_days.load_active_mapping_rules", AsyncMock(return_value={})),
    ):
        sale_days, inventory = await run_step2(db, velocity, ["sku-A"])

    assert direct_loader.await_args.kwargs["eu_countries"] == {"DE", "FR"}
    assert inventory["sku-A"]["EU"] == InventoryStock(available=7, reserved=2, in_transit=0)
    assert sale_days["sku-A"]["EU"] == 3.0


@pytest.mark.asyncio
async def test_run_step2_maps_third_party_component_inventory_to_commodity_stock() -> None:
    db = _FakeDb([])
    velocity = {"A": {"US": 1.0}}

    with (
        patch("app.engine.step2_sale_days.load_third_party_inventory", AsyncMock(return_value={})),
        patch("app.engine.step2_sale_days.load_in_transit", AsyncMock(return_value={})),
        patch(
            "app.engine.step2_sale_days.load_active_mapping_rules",
            AsyncMock(
                return_value={
                    "A": [
                        [
                            MappingComponent(inventory_sku="B", quantity=1),
                            MappingComponent(inventory_sku="C", quantity=2),
                        ]
                    ]
                }
            ),
        ),
        patch(
            "app.engine.step2_sale_days.load_third_party_component_inventory_by_warehouse",
            AsyncMock(
                return_value={
                    ("B", "third_party:1"): WarehouseStock(country="US", total=8),
                    ("C", "third_party:1"): WarehouseStock(country="US", total=6),
                }
            ),
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

    assert inventory["A"]["US"] == InventoryStock(available=3, reserved=0, in_transit=0)
    assert sale_days["A"]["US"] == 3.0


@pytest.mark.asyncio
async def test_run_step2_maps_eu_third_party_components_to_commodity_stock() -> None:
    db = _FakeDb([], config=SimpleNamespace(eu_countries=["DE", "FR"]))
    velocity = {"A": {"EU": 1.0}}
    component_loader = AsyncMock(
        return_value={
            ("B", "third_party:1"): WarehouseStock(country="EU", total=8),
            ("C", "third_party:1"): WarehouseStock(country="EU", total=6),
        }
    )

    with (
        patch("app.engine.step2_sale_days.load_third_party_inventory", AsyncMock(return_value={})),
        patch("app.engine.step2_sale_days.load_in_transit", AsyncMock(return_value={})),
        patch(
            "app.engine.step2_sale_days.load_active_mapping_rules",
            AsyncMock(
                return_value={
                    "A": [
                        [
                            MappingComponent(inventory_sku="B", quantity=1),
                            MappingComponent(inventory_sku="C", quantity=2),
                        ]
                    ]
                }
            ),
        ),
        patch(
            "app.engine.step2_sale_days.load_third_party_component_inventory_by_warehouse",
            component_loader,
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

    assert component_loader.await_args.kwargs["eu_countries"] == {"DE", "FR"}
    assert inventory["A"]["EU"] == InventoryStock(available=3, reserved=0, in_transit=0)
    assert sale_days["A"]["EU"] == 3.0


@pytest.mark.asyncio
async def test_run_step2_keeps_third_party_components_in_same_warehouse() -> None:
    db = _FakeDb([])
    velocity = {"A": {"US": 1.0}}

    with (
        patch("app.engine.step2_sale_days.load_third_party_inventory", AsyncMock(return_value={})),
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
            "app.engine.step2_sale_days.load_third_party_component_inventory_by_warehouse",
            AsyncMock(
                return_value={
                    ("B", "third_party:1"): WarehouseStock(country="US", total=10),
                    ("C", "third_party:2"): WarehouseStock(country="US", total=10),
                }
            ),
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
async def test_run_step2_keeps_eu_components_in_same_third_party_warehouse() -> None:
    db = _FakeDb([], config=SimpleNamespace(eu_countries=["DE", "FR"]))
    velocity = {"A": {"EU": 1.0}}

    with (
        patch("app.engine.step2_sale_days.load_third_party_inventory", AsyncMock(return_value={})),
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
            "app.engine.step2_sale_days.load_third_party_component_inventory_by_warehouse",
            AsyncMock(
                return_value={
                    ("B", "third_party:1"): WarehouseStock(country="EU", total=10),
                    ("C", "third_party:2"): WarehouseStock(country="EU", total=10),
                }
            ),
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

    assert inventory["A"]["EU"].total == 0
    assert sale_days["A"]["EU"] == 0.0


@pytest.mark.asyncio
async def test_run_step2_combines_third_party_components_with_country_level_transit() -> None:
    db = _FakeDb([])
    velocity = {"A": {"US": 1.0}}

    with (
        patch("app.engine.step2_sale_days.load_third_party_inventory", AsyncMock(return_value={})),
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
            "app.engine.step2_sale_days.load_third_party_component_inventory_by_warehouse",
            AsyncMock(
                return_value={
                    ("B", "third_party:1"): WarehouseStock(country="US", total=5),
                }
            ),
        ),
        patch(
            "app.engine.step2_sale_days.load_in_transit_totals_by_warehouse",
            AsyncMock(return_value={}),
        ),
        patch(
            "app.engine.step2_sale_days.load_in_transit_totals_by_country",
            AsyncMock(return_value={("C", "US"): 5}),
        ),
    ):
        sale_days, inventory = await run_step2(db, velocity, ["A"])

    assert inventory["A"]["US"].total == 5
    assert sale_days["A"]["US"] == 5.0


@pytest.mark.asyncio
async def test_run_step2_keeps_known_zero_inventory_records_for_composite_skus() -> None:
    db = _FakeDb([])
    velocity = {"A": {"US": 1.0}}

    with (
        patch("app.engine.step2_sale_days.load_third_party_inventory", AsyncMock(return_value={})),
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
            "app.engine.step2_sale_days.load_in_transit_totals_by_warehouse",
            AsyncMock(return_value={("B", "WH-US-1"): WarehouseStock(country="US", total=5)}),
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
async def test_run_step2_excludes_default_and_domestic_component_warehouse_transit() -> None:
    db = _FakeDb([])
    velocity = {"A": {"US": 1.0}}
    warehouse_transit_loader = AsyncMock(return_value={})

    with (
        patch("app.engine.step2_sale_days.load_third_party_inventory", AsyncMock(return_value={})),
        patch("app.engine.step2_sale_days.load_in_transit", AsyncMock(return_value={})),
        patch(
            "app.engine.step2_sale_days.load_active_mapping_rules",
            AsyncMock(return_value={"A": [[MappingComponent(inventory_sku="B", quantity=1)]]}),
        ),
        patch(
            "app.engine.step2_sale_days.load_in_transit_totals_by_warehouse",
            warehouse_transit_loader,
        ),
        patch(
            "app.engine.step2_sale_days.load_in_transit_totals_by_country",
            AsyncMock(return_value={}),
        ),
    ):
        await run_step2(db, velocity, ["A"])

    assert (
        warehouse_transit_loader.await_args.kwargs["exclude_warehouse_types"]
        == LOCAL_WAREHOUSE_TYPES
    )


@pytest.mark.asyncio
async def test_run_step2_uses_country_level_transit_without_double_counting_warehouse_stock() -> (
    None
):
    db = _FakeDb([])
    velocity = {"A": {"US": 1.0}}

    with (
        patch("app.engine.step2_sale_days.load_third_party_inventory", AsyncMock(return_value={})),
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
            "app.engine.step2_sale_days.load_in_transit_totals_by_warehouse",
            AsyncMock(
                return_value={
                    ("B", "WH-US-1"): WarehouseStock(country="US", total=5),
                    ("C", "WH-US-1"): WarehouseStock(country="US", total=5),
                }
            ),
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
    assert "warehouse" in compiled_sql
    assert "warehouse.type NOT IN" in compiled_sql
    assert _has_type_param(_compiled_params(db.statements[0]), LOCAL_WAREHOUSE_TYPES)
    assert "suggestion_item" not in compiled_sql
