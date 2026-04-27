from app.engine.sku_mapping import (
    MappingComponent,
    WarehouseStock,
    compute_mapped_stock_by_country,
    compute_mapped_stock_total_by_sku,
)


def test_single_component_mapping_uses_floor_per_warehouse() -> None:
    result = compute_mapped_stock_by_country(
        {"A": [MappingComponent(inventory_sku="B", quantity=2)]},
        {
            ("B", "WH-US-1"): WarehouseStock(country="US", total=5),
            ("B", "WH-US-2"): WarehouseStock(country="US", total=1),
        },
    )

    assert result == {("A", "US"): 2}


def test_multi_component_mapping_uses_min_per_warehouse() -> None:
    result = compute_mapped_stock_by_country(
        {
            "A": [
                MappingComponent(inventory_sku="B", quantity=1),
                MappingComponent(inventory_sku="C", quantity=2),
            ]
        },
        {
            ("B", "WH-US-1"): WarehouseStock(country="US", total=5),
            ("C", "WH-US-1"): WarehouseStock(country="US", total=6),
        },
    )

    assert result == {("A", "US"): 3}


def test_components_cannot_be_combined_across_warehouses() -> None:
    result = compute_mapped_stock_by_country(
        {
            "A": [
                MappingComponent(inventory_sku="B", quantity=1),
                MappingComponent(inventory_sku="C", quantity=1),
            ]
        },
        {
            ("B", "WH-US-1"): WarehouseStock(country="US", total=5),
            ("C", "WH-US-2"): WarehouseStock(country="US", total=5),
        },
    )

    assert result == {}


def test_local_mapping_does_not_require_country() -> None:
    result = compute_mapped_stock_total_by_sku(
        {"A": [MappingComponent(inventory_sku="B", quantity=2)]},
        {("B", "LOCAL-1"): WarehouseStock(country=None, total=7)},
    )

    assert result == {"A": 3}
