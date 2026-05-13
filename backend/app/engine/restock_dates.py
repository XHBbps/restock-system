"""Restock-date helpers.

User-visible restock dates are the demand date selected when generating a
suggestion, not a date derived from sale days or lead time.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date


def demand_restock_dates(
    country_qty_for_sku: Mapping[str, int],
    demand_date: date | str | None,
) -> dict[str, str | None]:
    restock_date = demand_date.isoformat() if isinstance(demand_date, date) else demand_date
    return {
        country: restock_date
        for country, qty in country_qty_for_sku.items()
        if int(qty or 0) > 0
    }
