"""Step 3 country_qty 单元测试：负数 clamping + overstock 收集。"""

from app.engine.step3_country_qty import compute_country_qty


def _make_inventory(stock_map: dict[str, dict[str, int]]) -> dict:
    """{sku: {country: total}} → {sku: {country: {total: ...}}}"""
    return {
        sku: {country: {"total": total} for country, total in country_map.items()}
        for sku, country_map in stock_map.items()
    }


def test_basic_compute() -> None:
    velocity = {"sku-A": {"JP": 10.0, "US": 5.0}}
    inventory = _make_inventory({"sku-A": {"JP": 300, "US": 100}})
    target = 60

    qty, overstock = compute_country_qty(velocity, inventory, target)
    # JP: raw = 60*10 - 300 = 300
    assert qty["sku-A"]["JP"] == 300
    # US: raw = 60*5 - 100 = 200
    assert qty["sku-A"]["US"] == 200
    assert overstock == {}


def test_negative_raw_clamped_to_zero_and_collected() -> None:
    velocity = {"sku-A": {"JP": 10.0, "US": 5.0}}
    inventory = _make_inventory({"sku-A": {"JP": 800, "US": 100}})
    target = 60

    qty, overstock = compute_country_qty(velocity, inventory, target)
    # JP: raw = 600-800 = -200 → 不入 country_qty + 入 overstock
    assert "JP" not in qty.get("sku-A", {})
    assert "JP" in overstock["sku-A"]
    # US: 200
    assert qty["sku-A"]["US"] == 200


def test_zero_velocity_skipped() -> None:
    velocity = {"sku-A": {"JP": 0.0, "US": 5.0}}
    inventory = _make_inventory({"sku-A": {"JP": 100, "US": 100}})
    qty, overstock = compute_country_qty(velocity, inventory, 60)
    assert "JP" not in qty.get("sku-A", {})
    assert "JP" not in overstock.get("sku-A", [])
    assert qty["sku-A"]["US"] == 200


def test_exact_target_yields_zero_not_overstock() -> None:
    """raw = 0 应该既不入 qty 也不入 overstock。"""
    velocity = {"sku-A": {"JP": 10.0}}
    inventory = _make_inventory({"sku-A": {"JP": 600}})  # 60*10
    qty, overstock = compute_country_qty(velocity, inventory, 60)
    assert "JP" not in qty.get("sku-A", {})
    assert "JP" not in overstock.get("sku-A", [])


def test_no_inventory_record_treated_as_zero_stock() -> None:
    velocity = {"sku-A": {"JP": 10.0}}
    inventory: dict = {}  # 没有任何库存记录
    qty, _ = compute_country_qty(velocity, inventory, 60)
    # raw = 600 - 0 = 600
    assert qty["sku-A"]["JP"] == 600
