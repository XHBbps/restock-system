"""Step 6: purchase timing."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TimingResult:
    t_purchase: dict[str, date]
    urgent: bool


def positive_qty_countries(country_qty_for_sku: Mapping[str, int]) -> set[str]:
    """Return countries whose replenishment qty is still positive."""
    return {country for country, qty in country_qty_for_sku.items() if qty > 0}


def parse_purchase_date(raw: date | str, *, fallback: date | None = None) -> date:
    """Parse purchase date from engine/api inputs."""
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        logger.warning("step6_parse_purchase_date_failed", raw_value=raw)
        if fallback is not None:
            return fallback
        from app.core.timezone import now_beijing

        return now_beijing().date()


def has_urgent_purchase(
    t_purchase_by_country: Mapping[str, date | str],
    *,
    today: date,
    countries: set[str] | None = None,
) -> bool:
    """Any effective purchase date on/before today means urgent."""
    effective_countries = set(t_purchase_by_country.keys()) if countries is None else countries
    for country in effective_countries:
        raw = t_purchase_by_country.get(country)
        if raw is None:
            continue
        if parse_purchase_date(raw, fallback=today) <= today:
            return True
    return False


def missing_timing_countries(
    country_qty_for_sku: Mapping[str, int],
    timing_by_country: Mapping[str, date | str],
) -> list[str]:
    """Return positive-qty countries that still have no timing value."""
    return sorted(
        country
        for country in positive_qty_countries(country_qty_for_sku)
        if timing_by_country.get(country) is None
    )


def compute_timing_for_sku(
    *,
    sale_days_for_sku: dict[str, float],
    country_qty_for_sku: dict[str, int],
    target_days: int,
    lead_time_days: int,
    today: date,
) -> TimingResult:
    """Compute purchase timing for each positive-qty country."""
    t_purchase: dict[str, date] = {}

    for country in positive_qty_countries(country_qty_for_sku):
        sale_days = sale_days_for_sku.get(country)
        if sale_days is None:
            logger.warning(
                "step6_sale_days_missing_treated_as_immediate_purchase",
                country=country,
                lead_time_days=lead_time_days,
            )
            t_purchase[country] = today
            continue

        purchase_offset = round(sale_days - target_days) - lead_time_days
        t_purchase[country] = today + timedelta(days=purchase_offset)

    return TimingResult(
        t_purchase=t_purchase,
        urgent=has_urgent_purchase(
            t_purchase,
            today=today,
            countries=positive_qty_countries(country_qty_for_sku),
        ),
    )
