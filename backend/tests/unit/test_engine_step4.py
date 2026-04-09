"""Step 4 total 单元测试：仅累加 country_qty>0 + 本地仓扣减 + max(0)。"""

from app.engine.step4_total import compute_total


def test_basic_total() -> None:
    # JP=0(积压, 不计) US=300 UK=200 DE=100
    total = compute_total(
        sku="sku-A",
        country_qty_for_sku={"JP": 0, "US": 300, "UK": 200, "DE": 100},
        velocity_for_sku={"JP": 8.6, "US": 10.0, "UK": 5.0, "DE": 4.0},
        local_stock_for_sku={"available": 300, "reserved": 200},
        buffer_days=30,
    )
    # Σ country_qty (qty>0) = 600
    # Σ velocity (qty>0)    = 19
    # buffer = 19 * 30 = 570
    # local = 500
    # total = 600 + 570 - 500 = 670
    assert total == 670


def test_excludes_zero_country_velocity() -> None:
    """积压国（country_qty=0）的 velocity 不应计入 buffer。"""
    total = compute_total(
        sku="sku-A",
        country_qty_for_sku={"JP": 0, "US": 100},
        velocity_for_sku={"JP": 100.0, "US": 10.0},  # JP velocity 巨大但被排除
        local_stock_for_sku={"available": 0, "reserved": 0},
        buffer_days=30,
    )
    # Σ qty = 100, Σ velocity = 10, buffer = 300, local = 0
    assert total == 400


def test_max_zero() -> None:
    """Huge local stock case: previously clamped to 0, but MEDIUM-N1
    invariant requires total_qty >= sum(country_breakdown), so the
    minimum is sum_qty. Only empty country_qty yields 0 (see
    test_empty_country_qty).
    """
    total = compute_total(
        sku="sku-A",
        country_qty_for_sku={"US": 100},
        velocity_for_sku={"US": 10.0},
        local_stock_for_sku={"available": 10000, "reserved": 0},
        buffer_days=30,
    )
    assert total == 100


def test_no_local_stock() -> None:
    total = compute_total(
        sku="sku-A",
        country_qty_for_sku={"US": 100},
        velocity_for_sku={"US": 10.0},
        local_stock_for_sku=None,
        buffer_days=30,
    )
    # 100 + 300 - 0 = 400
    assert total == 400


def test_step4_total_respects_sum_invariant() -> None:
    """MEDIUM-N1: total_qty must be >= sum(country_breakdown) even at low v.

    Single country v=0.1, buffer_days=0, local=1, qty=3 -> sum_qty=3.
    raw = 3 + 0 - 1 = 2 < sum_qty(3), must clamp up to 3.
    """
    total = compute_total(
        sku="sku-A",
        country_qty_for_sku={"US": 3},
        velocity_for_sku={"US": 0.1},
        local_stock_for_sku={"available": 1, "reserved": 0},
        buffer_days=0,
    )
    assert total >= 3


def test_empty_country_qty() -> None:
    total = compute_total(
        sku="sku-A",
        country_qty_for_sku={},
        velocity_for_sku={"US": 10.0},
        local_stock_for_sku=None,
        buffer_days=30,
    )
    assert total == 0
