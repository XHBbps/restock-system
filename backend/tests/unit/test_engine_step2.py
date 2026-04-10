"""Unit tests for Step 2 sale_days."""

from app.engine.step2_sale_days import compute_sale_days, merge_inventory


def test_merge_inventory_keeps_zero_transit_by_default() -> None:
    merged = merge_inventory(
        oversea={("sku-A", "US"): {"available": 10, "reserved": 2}},
        in_transit={},
    )

    assert merged["sku-A"]["US"] == {
        "available": 10,
        "reserved": 2,
        "in_transit": 0,
        "total": 12,
    }


def test_compute_sale_days_uses_total_stock() -> None:
    sale_days = compute_sale_days(
        velocity={"sku-A": {"US": 5.0}},
        inventory={"sku-A": {"US": {"available": 10, "reserved": 5, "in_transit": 0, "total": 15}}},
    )

    assert sale_days["sku-A"]["US"] == 3.0


def test_compute_sale_days_skips_zero_or_negative_velocity() -> None:
    sale_days = compute_sale_days(
        velocity={"sku-A": {"US": 0.0, "CA": -1.0, "UK": 2.0}},
        inventory={
            "sku-A": {
                "US": {"total": 20},
                "CA": {"total": 20},
                "UK": {"total": 6},
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
                "US": {"total": 8},
                "CA": {"total": 100},
            }
        },
    )

    assert sale_days == {"sku-A": {"US": 2.0}}
