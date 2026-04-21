from app.engine.context import EngineContext
from app.engine.step4_total import step4_total


def test_step4_new_purchase_formula() -> None:
    ctx = EngineContext(
        country_qty={"sku1": {"US": 60, "EU": 40}},
        velocity={"sku1": {"US": 3, "EU": 2}},
        local_stock={"sku1": {"available": 200, "reserved": 50}},
        buffer_days=30,
        safety_stock_days=15,
    )

    result = step4_total(ctx)

    assert result["sku1"]["purchase_qty"] == 75


def test_step4_allows_negative_purchase_qty() -> None:
    ctx = EngineContext(
        country_qty={"sku1": {"US": 100}},
        velocity={"sku1": {"US": 0}},
        local_stock={"sku1": {"available": 150, "reserved": 0}},
        buffer_days=30,
        safety_stock_days=15,
    )

    result = step4_total(ctx)

    assert result["sku1"]["purchase_qty"] == -50


def test_step4_velocity_sum_includes_all_countries() -> None:
    ctx = EngineContext(
        country_qty={"sku1": {"US": 0}},
        velocity={"sku1": {"US": 3, "JP": 2}},
        local_stock={"sku1": {"available": 0, "reserved": 0}},
        buffer_days=30,
        safety_stock_days=15,
    )

    result = step4_total(ctx)

    assert result["sku1"]["purchase_qty"] == 225
