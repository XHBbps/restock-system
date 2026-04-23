from app.engine.context import EngineContext, LocalStock
from app.engine.step4_total import compute_total, step4_total


def test_step4_new_purchase_formula() -> None:
    ctx = EngineContext(
        country_qty={"sku1": {"US": 60, "EU": 40}},
        velocity={"sku1": {"US": 3, "EU": 2}},
        local_stock={"sku1": LocalStock(available=20, reserved=5)},
        buffer_days=30,
        safety_stock_days=15,
    )

    result = step4_total(ctx)

    assert result["sku1"] == 150


def test_step4_clamps_negative_purchase_qty_to_zero() -> None:
    """本地库存过剩时 raw = -50 应被 clamp 到 0（DB 侧也有 CheckConstraint 双保险）。"""
    ctx = EngineContext(
        country_qty={"sku1": {"US": 100}},
        velocity={"sku1": {"US": 0}},
        local_stock={"sku1": LocalStock(available=150, reserved=0)},
        buffer_days=30,
        safety_stock_days=15,
    )

    result = step4_total(ctx)

    assert result["sku1"] == 0


def test_step4_velocity_sum_includes_all_countries() -> None:
    ctx = EngineContext(
        country_qty={"sku1": {"US": 0}},
        velocity={"sku1": {"US": 3, "JP": 2}},
        local_stock={"sku1": LocalStock(available=0, reserved=0)},
        buffer_days=30,
        safety_stock_days=15,
    )

    result = step4_total(ctx)

    assert result["sku1"] == 75


def test_step4_buffer_days_does_not_affect_purchase_qty() -> None:
    without_buffer = compute_total(
        sku="sku1",
        country_qty_for_sku={"US": 100},
        velocity_for_sku={"US": 3, "JP": 2},
        local_stock_for_sku=LocalStock(available=20, reserved=5),
        buffer_days=0,
        safety_stock_days=15,
    )
    with_buffer = compute_total(
        sku="sku1",
        country_qty_for_sku={"US": 100},
        velocity_for_sku={"US": 3, "JP": 2},
        local_stock_for_sku=LocalStock(available=20, reserved=5),
        buffer_days=30,
        safety_stock_days=15,
    )

    assert without_buffer == 150
    assert with_buffer == without_buffer
