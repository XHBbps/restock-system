"""Step 6: urgency calculation."""

from collections.abc import Mapping
from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class UrgencyResult:
    urgent: bool


def positive_qty_countries(country_qty_for_sku: Mapping[str, int]) -> set[str]:
    """Return countries whose replenishment qty is still positive."""
    return {country for country, qty in country_qty_for_sku.items() if qty > 0}


def has_urgent_sale_days(
    sale_days_by_country: Mapping[str, float | int | None],
    *,
    lead_time_days: int,
    countries: set[str] | None = None,
) -> bool:
    """Any effective country at or below lead time is urgent."""
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


def compute_urgency_for_sku(
    *,
    sale_days_for_sku: dict[str, float],
    country_qty_for_sku: dict[str, int],
    lead_time_days: int,
) -> UrgencyResult:
    """Compute urgent flag for each positive-qty SKU."""
    return UrgencyResult(
        urgent=has_urgent_sale_days(
            sale_days_for_sku,
            lead_time_days=lead_time_days,
            countries=positive_qty_countries(country_qty_for_sku),
        )
    )
