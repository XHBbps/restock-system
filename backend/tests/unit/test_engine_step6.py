from datetime import date, timedelta

from app.engine.step6_timing import (
    compute_urgency_for_sku,
    has_urgent_sale_days,
    positive_qty_countries,
    step6_timing,
)


def test_positive_qty_countries_only_keeps_positive_values() -> None:
    assert positive_qty_countries({"US": 10, "CA": 0, "JP": -1, "GB": 5}) == {"US", "GB"}


def test_compute_urgency_marks_sale_days_at_lead_time_as_urgent() -> None:
    result = compute_urgency_for_sku(
        sale_days_for_sku={"US": 20.0},
        country_qty_for_sku={"US": 10},
        lead_time_days=20,
    )

    assert result.urgent is True


def test_step6_purchase_date_with_min_sale_days() -> None:
    today = date(2026, 4, 20)

    result = step6_timing(
        sale_days_snapshot={"sku1": {"US": 30, "EU": 60}},
        purchase_qty={"sku1": 100},
        lead_time_by_sku={"sku1": 50},
        today=today,
    )

    assert result["sku1"]["purchase_date"] == today - timedelta(days=70)


def test_step6_no_purchase_date_when_zero_qty() -> None:
    result = step6_timing(
        sale_days_snapshot={"sku1": {"US": 30}},
        purchase_qty={"sku1": 0},
        lead_time_by_sku={"sku1": 50},
        today=date(2026, 4, 20),
    )

    assert result["sku1"]["purchase_date"] is None


def test_step6_no_purchase_date_when_no_sale_days() -> None:
    result = step6_timing(
        sale_days_snapshot={"sku1": {}},
        purchase_qty={"sku1": 100},
        lead_time_by_sku={"sku1": 50},
        today=date(2026, 4, 20),
    )

    assert result["sku1"]["purchase_date"] is None


def test_has_urgent_sale_days_accepts_numeric_values() -> None:
    urgent = has_urgent_sale_days(
        {"US": 8, "UK": 15.5},
        lead_time_days=10,
        countries={"US", "UK"},
    )

    assert urgent is True
