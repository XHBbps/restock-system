from datetime import date

from app.engine.step6_timing import (
    compute_restock_dates,
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


def test_step6_restock_dates_by_country() -> None:
    today = date(2026, 4, 20)

    result = step6_timing(
        sale_days_snapshot={"sku1": {"US": 30, "EU": 60}},
        lead_time_by_sku={"sku1": 20},
        country_qty={"sku1": {"US": 10, "EU": 5}},
        today=today,
    )

    assert result["sku1"]["restock_dates"] == {
        "US": "2026-04-30",
        "EU": "2026-05-30",
    }


def test_compute_restock_dates_skips_non_positive_country_qty_and_keeps_missing_as_none() -> None:
    restock_dates = compute_restock_dates(
        {"US": 30},
        country_qty_for_sku={"US": 10, "EU": 5, "JP": 0},
        lead_time_days=20,
        today=date(2026, 4, 20),
    )

    assert restock_dates == {"US": "2026-04-30", "EU": None}


def test_step6_ignores_skus_without_positive_country_qty_for_restock_dates() -> None:
    result = step6_timing(
        sale_days_snapshot={"sku1": {"US": 30}},
        lead_time_by_sku={"sku1": 50},
        country_qty={"sku1": {"US": 0}},
        today=date(2026, 4, 20),
    )

    assert result["sku1"]["restock_dates"] == {}


def test_has_urgent_sale_days_accepts_numeric_values() -> None:
    urgent = has_urgent_sale_days(
        {"US": 8, "UK": 15.5},
        lead_time_days=10,
        countries={"US", "UK"},
    )

    assert urgent is True
