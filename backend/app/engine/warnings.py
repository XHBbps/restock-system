"""Calculation warning helpers for suggestion items."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.countries import is_reportable_country_code

CalculationWarning = dict[str, str | None]

WARNING_MESSAGES: dict[str, str] = {
    "missing_inventory_record": "有销量但缺少库存或在途记录，未把未知库存按 0 参与补货计算",
    "country_added_after_generation": "该国家是在建议单生成后手工新增，缺少原始可售天数",
    "missing_velocity": "缺少该国家的销量速度，无法计算可售天数",
    "invalid_sale_days": "可售天数不是有效数值，无法计算紧急状态和补货日期",
    "non_reportable_country": "该国家不可用于报表或补货计算",
}


def warning_message(code: str) -> str:
    return WARNING_MESSAGES.get(code, "该条目存在无法自动解释的计算诊断")


def make_warning(code: str, country: str, *, reason: str | None = None) -> CalculationWarning:
    return {
        "code": code,
        "country": country,
        "reason": reason or code,
        "message": warning_message(code),
    }


def build_calculation_warnings(
    *,
    country_qty_for_sku: Mapping[str, Any],
    sale_days_for_sku: Mapping[str, Any] | None,
    velocity_for_sku: Mapping[str, Any] | None = None,
    added_countries: set[str] | None = None,
    missing_inventory_countries: set[str] | None = None,
) -> list[CalculationWarning]:
    """Build deterministic country diagnostics for one suggestion item.

    Warnings are intentionally non-blocking: they explain why dates/urgency may be
    missing or why a country was excluded from stock-sensitive calculations.
    """

    sale_days = sale_days_for_sku or {}
    velocity = velocity_for_sku or {}
    added = added_countries or set()
    missing_inventory = missing_inventory_countries or set()
    warnings: list[CalculationWarning] = []
    seen: set[tuple[str, str]] = set()

    candidate_countries = {
        str(country)
        for country, qty in country_qty_for_sku.items()
        if _positive_int(qty)
    }
    candidate_countries.update(str(country) for country in missing_inventory)

    for country in sorted(candidate_countries):
        code: str | None = None
        if not is_reportable_country_code(country):
            code = "non_reportable_country"
        elif country in missing_inventory:
            code = "missing_inventory_record"
        elif country not in sale_days:
            if country in added:
                code = "country_added_after_generation"
            elif velocity and country not in velocity:
                code = "missing_velocity"
            else:
                code = "missing_velocity"
        else:
            try:
                float(sale_days[country])
            except (TypeError, ValueError):
                code = "invalid_sale_days"

        if code is None:
            continue
        key = (code, country)
        if key in seen:
            continue
        seen.add(key)
        warnings.append(make_warning(code, country))

    return warnings


def _positive_int(value: Any) -> bool:
    try:
        return int(value or 0) > 0
    except (TypeError, ValueError):
        return False
