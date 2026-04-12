"""Step 6:采购 / 发货时间。

公式(FR-035):
    T_发货[国] = 今天 + round(sale_days[国] - TARGET_DAYS) 天
    T_采购[国] = T_发货 - lead_time 天
    lead_time 优先 sku_config.lead_time_days,缺省用全局 LEAD_TIME_DAYS

    SKU 级 urgent 标记:若任一国 T_采购 <= 今天 -> urgent = true
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TimingResult:
    t_ship: dict[str, date]  # country -> date
    t_purchase: dict[str, date]  # country -> date
    urgent: bool  # 任一国 T_采购 <= today


def positive_qty_countries(country_qty_for_sku: Mapping[str, int]) -> set[str]:
    """返回当前仍需要采购的国家集合。"""
    return {country for country, qty in country_qty_for_sku.items() if qty > 0}


def parse_purchase_date(raw: date | str, *, fallback: date | None = None) -> date:
    """兼容 engine(date) 与 PATCH API(str) 两种输入。

    解析失败时返回 fallback(默认 today),保守视为紧急。
    """
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
    """统一 urgent 规则: 任一有效采购国的 T_采购 <= today。"""
    effective_countries = set(t_purchase_by_country.keys()) if countries is None else countries
    for country in effective_countries:
        raw = t_purchase_by_country.get(country)
        if raw is None:
            continue
        if parse_purchase_date(raw) <= today:
            return True
    return False


def missing_timing_countries(
    country_qty_for_sku: Mapping[str, int],
    timing_by_country: Mapping[str, date | str],
) -> list[str]:
    """找出所有 qty>0 但缺少时间字段的国家。"""
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
    """对单个 SKU 计算所有 country_qty>0 国家的时间节点。"""
    t_ship: dict[str, date] = {}
    t_purchase: dict[str, date] = {}

    for country in positive_qty_countries(country_qty_for_sku):
        sd = sale_days_for_sku.get(country)
        if sd is None:
            # 显式口径: 若仍需采购,但缺少 sale_days,则视为无法等待库存自然覆盖,
            # 采购日立即落到 today,发货日维持 today + lead_time。
            logger.warning(
                "step6_sale_days_missing_treated_as_immediate_purchase",
                country=country,
                lead_time_days=lead_time_days,
            )
            ship_date = today + timedelta(days=lead_time_days)
            purchase_date = ship_date - timedelta(days=lead_time_days)
            t_ship[country] = ship_date
            t_purchase[country] = purchase_date
            continue
        ship_offset = round(sd - target_days)
        ship_date = today + timedelta(days=ship_offset)
        purchase_date = ship_date - timedelta(days=lead_time_days)
        t_ship[country] = ship_date
        t_purchase[country] = purchase_date

    return TimingResult(
        t_ship=t_ship,
        t_purchase=t_purchase,
        urgent=has_urgent_purchase(
            t_purchase,
            today=today,
            countries=positive_qty_countries(country_qty_for_sku),
        ),
    )
