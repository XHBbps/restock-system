"""Step 6: urgency and purchase-date calculation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class UrgencyResult:
    urgent: bool
    purchase_date: date | None = None


def positive_qty_countries(country_qty_for_sku: Mapping[str, int]) -> set[str]:
    return {country for country, qty in country_qty_for_sku.items() if qty > 0}


def has_urgent_sale_days(
    sale_days_by_country: Mapping[str, float | int | None],
    *,
    lead_time_days: int,
    countries: set[str] | None = None,
) -> bool:
    effective_countries = set(sale_days_by_country.keys()) if countries is None else countries
    for country in effective_countries:
        raw = sale_days_by_country.get(country)
        if raw is None:
            logger.warning("step6_sale_days_missing_ignored_for_urgency", country=country)
            continue
        try:
            sale_days = float(raw)
        except (TypeError, ValueError):
            logger.warning(
                "step6_sale_days_invalid_ignored_for_urgency",
                country=country,
                raw_value=raw,
            )
            continue
        if sale_days <= lead_time_days:
            return True
    return False


def compute_purchase_date(
    sale_days_by_country: Mapping[str, float | int | None],
    *,
    purchase_qty: int,
    lead_time_days: int,
    today: date,
) -> date | None:
    if purchase_qty <= 0:
        return None
    valid: list[float] = []
    for raw in sale_days_by_country.values():
        if raw is None:
            continue
        try:
            valid.append(float(raw))
        except (TypeError, ValueError):
            continue
    if not valid:
        return None
    min_sale_days = min(valid)
    return today + timedelta(days=int(min_sale_days) - 2 * lead_time_days)


def compute_urgency_for_sku(
    *,
    sale_days_for_sku: Mapping[str, float | int | None],
    country_qty_for_sku: Mapping[str, int],
    lead_time_days: int,
    purchase_qty: int = 0,
    today: date | None = None,
) -> UrgencyResult:
    effective_today = today or date.today()
    return UrgencyResult(
        urgent=has_urgent_sale_days(
            sale_days_for_sku,
            lead_time_days=lead_time_days,
            countries=positive_qty_countries(country_qty_for_sku),
        ),
        purchase_date=compute_purchase_date(
            sale_days_for_sku,
            purchase_qty=purchase_qty,
            lead_time_days=lead_time_days,
            today=effective_today,
        ),
    )


def step6_timing(
    *,
    sale_days_snapshot: dict[str, dict[str, float | None]],
    purchase_qty: dict[str, int],
    lead_time_by_sku: dict[str, int],
    country_qty: dict[str, dict[str, int]] | None = None,
    today: date | None = None,
) -> dict[str, dict[str, Any]]:
    effective_today = today or date.today()
    result: dict[str, dict[str, Any]] = {}
    all_skus = set(sale_days_snapshot) | set(purchase_qty) | set(lead_time_by_sku)
    for sku in all_skus:
        urgency = compute_urgency_for_sku(
            sale_days_for_sku=sale_days_snapshot.get(sku, {}),
            country_qty_for_sku=(country_qty or {}).get(sku, {}),
            lead_time_days=lead_time_by_sku.get(sku, 50),
            purchase_qty=purchase_qty.get(sku, 0),
            today=effective_today,
        )
        result[sku] = {
            "urgent": urgency.urgent,
            "purchase_date": urgency.purchase_date,
        }
    return result
