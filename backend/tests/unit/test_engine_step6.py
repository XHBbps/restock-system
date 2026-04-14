"""Unit tests for step6 urgency helpers."""

from app.engine.step6_timing import (
    compute_urgency_for_sku,
    has_urgent_sale_days,
    positive_qty_countries,
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


def test_compute_urgency_ignores_non_positive_countries() -> None:
    result = compute_urgency_for_sku(
        sale_days_for_sku={"US": 10.0, "CA": 2.0},
        country_qty_for_sku={"US": 0, "CA": 0},
        lead_time_days=5,
    )

    assert result.urgent is False


def test_has_urgent_sale_days_accepts_numeric_values() -> None:
    urgent = has_urgent_sale_days(
        {"US": 8, "UK": 15.5},
        lead_time_days=10,
        countries={"US", "UK"},
    )

    assert urgent is True


def test_has_urgent_sale_days_keeps_empty_country_set_empty() -> None:
    urgent = has_urgent_sale_days(
        {"US": 1},
        lead_time_days=10,
        countries=set(),
    )

    assert urgent is False


def test_has_urgent_sale_days_ignores_missing_country() -> None:
    assert has_urgent_sale_days({}, lead_time_days=10, countries={"US"}) is False


def test_has_urgent_sale_days_ignores_invalid_value() -> None:
    assert has_urgent_sale_days({"US": "bad"}, lead_time_days=10, countries={"US"}) is False


def test_has_urgent_sale_days_still_uses_other_valid_countries() -> None:
    urgent = has_urgent_sale_days(
        {"US": None, "CA": 8},
        lead_time_days=10,
        countries={"US", "CA"},
    )

    assert urgent is True
