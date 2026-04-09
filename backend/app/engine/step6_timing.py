"""Step 6：采购 / 发货时间。

公式（FR-035）：
    T_发货[国] = 今天 + round(sale_days[国] − TARGET_DAYS) 天
    T_采购[国] = T_发货 − lead_time 天
    lead_time 优先 sku_config.lead_time_days，缺省用全局 LEAD_TIME_DAYS

    SKU 级 urgent 标记：若任一国 T_采购 ≤ 今天 → urgent = true
"""

from dataclasses import dataclass
from datetime import date, timedelta

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TimingResult:
    t_ship: dict[str, date]  # country → date
    t_purchase: dict[str, date]  # country → date
    urgent: bool  # 任一国 T_采购 ≤ today


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
    urgent = False

    for country, qty in country_qty_for_sku.items():
        if qty <= 0:
            continue
        sd = sale_days_for_sku.get(country)
        if sd is None:
            # Missing sale_days (edge case: velocity=0 but country_qty>0).
            # Fall back to today + lead_time so t_purchase/t_ship stay complete.
            logger.warning(
                "step6_sale_days_missing_fallback",
                country=country,
                qty=qty,
                lead_time_days=lead_time_days,
            )
            ship_date = today + timedelta(days=lead_time_days)
            purchase_date = ship_date - timedelta(days=lead_time_days)
            t_ship[country] = ship_date
            t_purchase[country] = purchase_date
            if purchase_date <= today:
                urgent = True
            continue
        ship_offset = round(sd - target_days)
        ship_date = today + timedelta(days=ship_offset)
        purchase_date = ship_date - timedelta(days=lead_time_days)
        t_ship[country] = ship_date
        t_purchase[country] = purchase_date
        if purchase_date <= today:
            urgent = True

    return TimingResult(t_ship=t_ship, t_purchase=t_purchase, urgent=urgent)
