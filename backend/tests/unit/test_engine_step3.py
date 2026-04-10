"""Step 3 country_qty 单元测试:负数 clamping。"""

from app.engine.step3_country_qty import compute_country_qty


def _make_inventory(stock_map: dict[str, dict[str, int]]) -> dict:
    """{sku: {country: total}} -> {sku: {country: {total: ...}}}"""
    return {
        sku: {country: {"total": total} for country, total in country_map.items()}
        for sku, country_map in stock_map.items()
    }


def test_basic_compute() -> None:
    velocity = {"sku-A": {"JP": 10.0, "US": 5.0}}
    inventory = _make_inventory({"sku-A": {"JP": 300, "US": 100}})
    target = 60

    qty = compute_country_qty(velocity, inventory, target)
    assert qty["sku-A"]["JP"] == 300
    assert qty["sku-A"]["US"] == 200


def test_negative_raw_clamped_to_zero() -> None:
    velocity = {"sku-A": {"JP": 10.0, "US": 5.0}}
    inventory = _make_inventory({"sku-A": {"JP": 800, "US": 100}})
    target = 60

    qty = compute_country_qty(velocity, inventory, target)
    assert "JP" not in qty.get("sku-A", {})
    assert qty["sku-A"]["US"] == 200


def test_zero_velocity_skipped() -> None:
    velocity = {"sku-A": {"JP": 0.0, "US": 5.0}}
    inventory = _make_inventory({"sku-A": {"JP": 100, "US": 100}})
    qty = compute_country_qty(velocity, inventory, 60)
    assert "JP" not in qty.get("sku-A", {})
    assert qty["sku-A"]["US"] == 200


def test_exact_target_yields_zero() -> None:
    """raw = 0 应该不入 qty。"""
    velocity = {"sku-A": {"JP": 10.0}}
    inventory = _make_inventory({"sku-A": {"JP": 600}})
    qty = compute_country_qty(velocity, inventory, 60)
    assert "JP" not in qty.get("sku-A", {})


def test_no_inventory_record_treated_as_zero_stock() -> None:
    velocity = {"sku-A": {"JP": 10.0}}
    inventory: dict = {}
    qty = compute_country_qty(velocity, inventory, 60)
    assert qty["sku-A"]["JP"] == 600
