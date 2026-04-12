"""Step 6 timing 单元测试:缺失 sale_days 语义 + urgent 共用规则。"""

from datetime import date

from app.engine.step6_timing import (
    compute_timing_for_sku,
    has_urgent_purchase,
    missing_timing_countries,
)


def test_compute_timing_basic_non_urgent() -> None:
    today = date(2026, 4, 9)
    result = compute_timing_for_sku(
        sale_days_for_sku={"US": 40.0},
        country_qty_for_sku={"US": 10},
        target_days=30,
        lead_time_days=5,
        today=today,
    )

    assert result.t_ship["US"] == date(2026, 4, 19)
    assert result.t_purchase["US"] == date(2026, 4, 14)
    assert result.urgent is False


def test_missing_sale_days_means_immediate_purchase() -> None:
    today = date(2026, 4, 9)
    result = compute_timing_for_sku(
        sale_days_for_sku={},
        country_qty_for_sku={"US": 10},
        target_days=30,
        lead_time_days=7,
        today=today,
    )

    assert result.t_purchase["US"] == today
    assert result.t_ship["US"] == date(2026, 4, 16)
    assert result.urgent is True


def test_missing_timing_countries_only_reports_positive_qty() -> None:
    missing = missing_timing_countries(
        {"US": 10, "CA": 0, "UK": 5},
        {"US": "2026-04-10"},
    )

    assert missing == ["UK"]


def test_has_urgent_purchase_accepts_iso_strings() -> None:
    urgent = has_urgent_purchase(
        {"US": "2026-04-09", "UK": "2026-04-15"},
        today=date(2026, 4, 9),
        countries={"US", "UK"},
    )

    assert urgent is True


def test_has_urgent_purchase_keeps_empty_country_set_empty() -> None:
    urgent = has_urgent_purchase(
        {"US": "2026-04-01"},
        today=date(2026, 4, 9),
        countries=set(),
    )

    assert urgent is False


def test_parse_purchase_date_invalid_format_returns_today():
    """P1-7: 非 ISO 格式不应崩溃,保守返回 today。"""
    from app.engine.step6_timing import has_urgent_purchase

    result = has_urgent_purchase(
        {"US": "not-a-date"},
        today=date(2026, 4, 12),
    )
    assert result is True  # 格式错误 → 视为紧急
