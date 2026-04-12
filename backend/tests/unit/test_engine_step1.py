"""Step 1 velocity 单元测试:日期分桶 + effective 公式 + 边界。"""

from datetime import date, timedelta

from app.engine.step1_velocity import (
    aggregate_velocity_from_items,
    compute_velocity,
    is_in_window,
)


def test_compute_velocity_formula() -> None:
    # 7 日 70 件 -> 日均 10
    # 14 日 112 件 -> 日均 8
    # 30 日 180 件 -> 日均 6
    v = compute_velocity(70, 112, 180)
    assert v == 10 * 0.5 + 8 * 0.3 + 6 * 0.2  # = 8.6


def test_compute_velocity_zero() -> None:
    assert compute_velocity(0, 0, 0) == 0


def test_is_in_window_yesterday_inclusive() -> None:
    today = date(2026, 4, 8)
    yesterday = date(2026, 4, 7)
    assert is_in_window(yesterday, today, 7) is True
    assert is_in_window(today, today, 7) is False  # 今天不在窗口


def test_is_in_window_lower_boundary() -> None:
    today = date(2026, 4, 8)
    # 7 日窗口 = [4-1, 4-7]
    assert is_in_window(date(2026, 4, 1), today, 7) is True
    assert is_in_window(date(2026, 3, 31), today, 7) is False


def test_aggregate_basic() -> None:
    today = date(2026, 4, 8)
    # 7 日窗口内每天 10 件 -> d7=70 d14=70 d30=70
    items = [
        ("sku-A", "JP", today - timedelta(days=i), 10, 0)
        for i in range(1, 8)  # i=1..7 -> 4-1..4-7
    ]
    result = aggregate_velocity_from_items(items, today)
    assert "sku-A" in result
    v = result["sku-A"]["JP"]
    expected = (70 / 7) * 0.5 + (70 / 14) * 0.3 + (70 / 30) * 0.2
    assert abs(v - expected) < 1e-9


def test_aggregate_refund_subtracted() -> None:
    today = date(2026, 4, 8)
    items = [
        ("sku-A", "JP", today - timedelta(days=1), 10, 3),  # effective = 7
        ("sku-A", "JP", today - timedelta(days=2), 5, 5),  # effective = 0
        ("sku-A", "JP", today - timedelta(days=3), 8, 10),  # effective = max(8-10,0)=0
    ]
    result = aggregate_velocity_from_items(items, today)
    # 7 日窗口共 7 件
    v = result["sku-A"]["JP"]
    expected = (7 / 7) * 0.5 + (7 / 14) * 0.3 + (7 / 30) * 0.2
    assert abs(v - expected) < 1e-9


def test_aggregate_outside_window_excluded() -> None:
    today = date(2026, 4, 8)
    items = [
        ("sku-A", "JP", today - timedelta(days=1), 10, 0),  # in
        ("sku-A", "JP", today - timedelta(days=40), 100, 0),  # 40 天前,不在窗口
        ("sku-A", "JP", today, 50, 0),  # 今天,不在窗口
    ]
    result = aggregate_velocity_from_items(items, today)
    v = result["sku-A"]["JP"]
    # 只有 1 条 10 件入窗口
    expected = (10 / 7) * 0.5 + (10 / 14) * 0.3 + (10 / 30) * 0.2
    assert abs(v - expected) < 1e-9


def test_aggregate_multi_country() -> None:
    today = date(2026, 4, 8)
    items = [
        ("sku-A", "JP", today - timedelta(days=1), 10, 0),
        ("sku-A", "US", today - timedelta(days=1), 20, 0),
    ]
    result = aggregate_velocity_from_items(items, today)
    assert set(result["sku-A"].keys()) == {"JP", "US"}
    assert result["sku-A"]["US"] > result["sku-A"]["JP"]


def test_aggregate_empty() -> None:
    assert aggregate_velocity_from_items([], date(2026, 4, 8)) == {}
