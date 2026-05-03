from app.engine.sku_mapping import (
    MappingComponent,
    WarehouseStock,
    compute_mapped_stock_by_country,
    compute_mapped_stock_total_by_sku,
)


def test_single_component_mapping_uses_floor_per_warehouse() -> None:
    result = compute_mapped_stock_by_country(
        {"A": [[MappingComponent(inventory_sku="B", quantity=2)]]},
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
                [
                    MappingComponent(inventory_sku="B", quantity=1),
                    MappingComponent(inventory_sku="C", quantity=2),
                ]
            ]
        },
        {
            ("B", "WH-US-1"): WarehouseStock(country="US", total=5),
            ("C", "WH-US-1"): WarehouseStock(country="US", total=6),
        },
    )

    assert result == {("A", "US"): 3}


def test_shared_overseas_components_are_allocated_by_country_velocity() -> None:
    result = compute_mapped_stock_by_country(
        {
            "A": [
                [
                    MappingComponent(inventory_sku="B", quantity=1),
                    MappingComponent(inventory_sku="C", quantity=1),
                    MappingComponent(inventory_sku="D", quantity=1),
                ]
            ],
            "A1": [
                [
                    MappingComponent(inventory_sku="B", quantity=1),
                    MappingComponent(inventory_sku="C", quantity=1),
                    MappingComponent(inventory_sku="E", quantity=1),
                ]
            ],
        },
        {
            ("B", "WH-US-1"): WarehouseStock(country="US", total=100),
            ("C", "WH-US-1"): WarehouseStock(country="US", total=100),
            ("D", "WH-US-1"): WarehouseStock(country="US", total=100),
            ("E", "WH-US-1"): WarehouseStock(country="US", total=100),
        },
        velocity={
            "A": {"US": 3.0},
            "A1": {"US": 1.0},
        },
    )

    assert result == {("A", "US"): 75, ("A1", "US"): 25}


def test_shared_overseas_components_equal_split_when_any_consumer_missing_velocity() -> None:
    result = compute_mapped_stock_by_country(
        {
            "A": [[MappingComponent(inventory_sku="B", quantity=1)]],
            "A1": [[MappingComponent(inventory_sku="B", quantity=1)]],
        },
        {("B", "WH-US-1"): WarehouseStock(country="US", total=9)},
        velocity={"A": {"US": 3.0}, "A1": {}},
    )

    assert result == {("A", "US"): 5, ("A1", "US"): 4}


def test_components_cannot_be_combined_across_warehouses() -> None:
    result = compute_mapped_stock_by_country(
        {
            "A": [
                [
                    MappingComponent(inventory_sku="B", quantity=1),
                    MappingComponent(inventory_sku="C", quantity=1),
                ]
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
        {"A": [[MappingComponent(inventory_sku="B", quantity=2)]]},
        {("B", "LOCAL-1"): WarehouseStock(country=None, total=7)},
    )

    assert result == {"A": 3}


def test_local_alternative_groups_sum_without_country() -> None:
    result = compute_mapped_stock_total_by_sku(
        {
            "A": [
                [MappingComponent(inventory_sku="B", quantity=2)],
                [
                    MappingComponent(inventory_sku="C", quantity=1),
                    MappingComponent(inventory_sku="D", quantity=3),
                ],
            ]
        },
        {
            ("B", "LOCAL-1"): WarehouseStock(country=None, total=7),
            ("C", "LOCAL-1"): WarehouseStock(country=None, total=5),
            ("D", "LOCAL-1"): WarehouseStock(country=None, total=8),
        },
    )

    assert result == {"A": 5}


def test_shared_local_components_are_allocated_by_total_velocity() -> None:
    result = compute_mapped_stock_total_by_sku(
        {
            "A": [[MappingComponent(inventory_sku="B", quantity=1)]],
            "A1": [[MappingComponent(inventory_sku="B", quantity=1)]],
        },
        {("B", "LOCAL-1"): WarehouseStock(country=None, total=9)},
        velocity={
            "A": {"US": 2.0, "CA": 1.0},
            "A1": {"US": 1.0},
        },
    )

    assert result == {"A": 7, "A1": 2}


def test_alternative_single_component_groups_sum_within_warehouse() -> None:
    result = compute_mapped_stock_by_country(
        {
            "A": [
                [MappingComponent(inventory_sku="B", quantity=2)],
                [MappingComponent(inventory_sku="C", quantity=3)],
                [MappingComponent(inventory_sku="D", quantity=1)],
            ]
        },
        {
            ("B", "WH-US-1"): WarehouseStock(country="US", total=5),
            ("C", "WH-US-1"): WarehouseStock(country="US", total=7),
            ("D", "WH-US-1"): WarehouseStock(country="US", total=4),
        },
    )

    assert result == {("A", "US"): 8}


def test_alternative_multi_component_groups_sum_each_group_min() -> None:
    result = compute_mapped_stock_by_country(
        {
            "A": [
                [
                    MappingComponent(inventory_sku="B", quantity=1),
                    MappingComponent(inventory_sku="C", quantity=2),
                    MappingComponent(inventory_sku="D", quantity=1),
                ],
                [
                    MappingComponent(inventory_sku="E", quantity=1),
                    MappingComponent(inventory_sku="F", quantity=1),
                    MappingComponent(inventory_sku="G", quantity=3),
                ],
            ]
        },
        {
            ("B", "WH-US-1"): WarehouseStock(country="US", total=6),
            ("C", "WH-US-1"): WarehouseStock(country="US", total=7),
            ("D", "WH-US-1"): WarehouseStock(country="US", total=8),
            ("E", "WH-US-1"): WarehouseStock(country="US", total=9),
            ("F", "WH-US-1"): WarehouseStock(country="US", total=4),
            ("G", "WH-US-1"): WarehouseStock(country="US", total=10),
        },
    )

    assert result == {("A", "US"): 6}
