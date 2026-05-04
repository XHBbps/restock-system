from datetime import date

import pytest

from app.engine.sku_mapping import MappingComponent, WarehouseStock, compute_mapped_stock_by_country
from app.engine.step1_velocity import aggregate_velocity_from_items
from app.schemas.config import PhysicalItemGroupIn
from app.services.physical_item import PhysicalSkuResolver


def test_physical_item_group_members_are_required_and_deduped() -> None:
    with pytest.raises(ValueError, match="成员 SKU 重复"):
        PhysicalItemGroupIn(name="库存组件A", members=["SKU-A", "SKU-A"])


def test_physical_resolver_falls_back_to_raw_sku_when_group_missing_or_disabled() -> None:
    resolver = PhysicalSkuResolver(
        sku_to_group_key={"SKU-A-OLD": "physical-group:1"},
        members_by_group_key={"physical-group:1": ["SKU-A", "SKU-A-OLD"]},
    )

    assert resolver.resolve_inventory_sku("SKU-A-OLD") == "physical-group:1"
    assert resolver.resolve_inventory_sku("SKU-B") == "SKU-B"
    assert resolver.expand_inventory_skus(["physical-group:1", "SKU-B"]) == [
        "SKU-A",
        "SKU-A-OLD",
        "SKU-B",
    ]


def test_step1_keeps_product_skus_separate_from_inventory_shared_groups() -> None:
    result = aggregate_velocity_from_items(
        [
            ("SKU-A", "US", date(2026, 5, 3), 7, 0),
            ("SKU-A-OLD", "US", date(2026, 5, 3), 7, 0),
        ],
        date(2026, 5, 4),
    )

    expected = (7 / 7) * 0.5 + (7 / 14) * 0.3 + (7 / 30) * 0.2
    assert result["SKU-A"]["US"] == expected
    assert result["SKU-A-OLD"]["US"] == expected


def test_mapping_components_can_be_normalized_before_existing_formula_logic() -> None:
    result = compute_mapped_stock_by_country(
        {"SKU-A": [[MappingComponent(inventory_sku="PKG-A", quantity=1)]]},
        {
            ("PKG-A", "WH-US-1"): WarehouseStock(country="US", total=5),
            ("PKG-A", "WH-US-2"): WarehouseStock(country="US", total=7),
        },
    )

    assert result == {("SKU-A", "US"): 12}
