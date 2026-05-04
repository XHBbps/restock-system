from datetime import date

import pytest

from app.engine.sku_mapping import MappingComponent, WarehouseStock, compute_mapped_stock_by_country
from app.engine.step1_velocity import aggregate_velocity_from_items
from app.schemas.config import PhysicalItemGroupIn
from app.services.physical_item import PhysicalSkuResolver


def test_physical_item_group_requires_primary_sku_in_aliases() -> None:
    with pytest.raises(ValueError, match="主 SKU 必须属于别名成员"):
        PhysicalItemGroupIn(name="同物A", primary_sku="SKU-A", aliases=["SKU-A-OLD"])


def test_physical_resolver_falls_back_to_raw_sku_when_group_missing_or_disabled() -> None:
    resolver = PhysicalSkuResolver(alias_to_primary={"SKU-A-OLD": "SKU-A"}, aliases_by_primary={})

    assert resolver.resolve("SKU-A-OLD") == "SKU-A"
    assert resolver.resolve("SKU-B") == "SKU-B"


def test_step1_aggregates_alias_sales_to_primary_sku() -> None:
    result = aggregate_velocity_from_items(
        [
            ("SKU-A", "US", date(2026, 5, 3), 7, 0),
            ("SKU-A-OLD", "US", date(2026, 5, 3), 7, 0),
        ],
        date(2026, 5, 4),
        sku_alias_map={"SKU-A-OLD": "SKU-A"},
    )

    assert result["SKU-A"]["US"] == (14 / 7) * 0.5 + (14 / 14) * 0.3 + (14 / 30) * 0.2
    assert "SKU-A-OLD" not in result


def test_mapping_components_can_be_normalized_before_existing_formula_logic() -> None:
    result = compute_mapped_stock_by_country(
        {"SKU-A": [[MappingComponent(inventory_sku="PKG-A", quantity=1)]]},
        {
            ("PKG-A", "WH-US-1"): WarehouseStock(country="US", total=5),
            ("PKG-A", "WH-US-2"): WarehouseStock(country="US", total=7),
        },
    )

    assert result == {("SKU-A", "US"): 12}
