"""Step 1：动销速度（按 SKU × 国家二维矩阵）。

公式（FR-028）：
    effective[order_item] = max(quantity_shipped - refund_num, 0)
    过滤 order_status ∈ {Shipped, PartiallyShipped}
    过滤 purchase_date ∈ [昨天-29, 昨天]（不含今天）
    按 (commodity_sku, country, date) 聚合 SUM(effective)

    day7_sum  = Σ effective where date ∈ [昨天-6, 昨天]
    day14_sum = Σ effective where date ∈ [昨天-13, 昨天]
    day30_sum = Σ effective where date ∈ [昨天-29, 昨天]

    velocity = day7/7 × 0.5 + day14/14 × 0.3 + day30/30 × 0.2
"""

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import BEIJING
from app.models.order import OrderHeader, OrderItem

VALID_STATUSES = ("Shipped", "PartiallyShipped")
WINDOW_DAYS = 30


def compute_velocity(day7_sum: int, day14_sum: int, day30_sum: int) -> float:
    """加权移动平均公式。

    暴露为独立函数便于单测。
    """
    return day7_sum / 7 * 0.5 + day14_sum / 14 * 0.3 + day30_sum / 30 * 0.2


def is_in_window(order_date: date, today: date, days_ago: int) -> bool:
    """订单日期是否落在 [昨天-days_ago+1, 昨天] 窗口内。"""
    yesterday = today - timedelta(days=1)
    earliest = yesterday - timedelta(days=days_ago - 1)
    return earliest <= order_date <= yesterday


def aggregate_velocity_from_items(
    items: list[tuple[str, str, date, int, int]],
    today: date,
) -> dict[str, dict[str, float]]:
    """从订单明细聚合 velocity（暴露为纯函数便于单测）。

    items: list of (commodity_sku, country, order_date, quantity_shipped, refund_num)
    返回：velocity[commodity_sku][country] = float
    """
    # bucket: {(sku, country): {date: effective}}
    daily: defaultdict[tuple[str, str], defaultdict[date, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for sku, country, d, shipped, refund in items:
        eff = max(int(shipped or 0) - int(refund or 0), 0)
        if eff <= 0:
            continue
        daily[(sku, country)][d] += eff

    result: defaultdict[str, dict[str, float]] = defaultdict(dict)
    for (sku, country), date_map in daily.items():
        d7_sum = sum(qty for d, qty in date_map.items() if is_in_window(d, today, 7))
        d14_sum = sum(qty for d, qty in date_map.items() if is_in_window(d, today, 14))
        d30_sum = sum(qty for d, qty in date_map.items() if is_in_window(d, today, 30))
        result[sku][country] = compute_velocity(d7_sum, d14_sum, d30_sum)
    return dict(result)


async def load_velocity_inputs(
    db: AsyncSession,
    *,
    commodity_skus: list[str] | None,
    today: date,
) -> list[tuple[str, str, date, int, int]]:
    """从数据库加载 Step 1 计算所需的订单明细行。"""
    yesterday = today - timedelta(days=1)
    earliest = yesterday - timedelta(days=WINDOW_DAYS - 1)
    earliest_dt = datetime.combine(earliest, datetime.min.time(), tzinfo=BEIJING)
    end_dt = datetime.combine(today, datetime.min.time(), tzinfo=BEIJING)

    stmt = (
        select(
            OrderItem.commodity_sku,
            OrderHeader.country_code,
            func.date(func.timezone("Asia/Shanghai", OrderHeader.purchase_date)).label(
                "order_date"
            ),
            OrderItem.quantity_shipped,
            OrderItem.refund_num,
        )
        .join(OrderHeader, OrderHeader.id == OrderItem.order_id)
        .where(OrderHeader.order_status.in_(VALID_STATUSES))
        .where(OrderHeader.purchase_date >= earliest_dt)
        .where(OrderHeader.purchase_date < end_dt)
    )
    if commodity_skus is not None:
        stmt = stmt.where(OrderItem.commodity_sku.in_(commodity_skus))

    rows = (await db.execute(stmt)).all()
    return [(r[0], r[1], r[2], r[3] or 0, r[4] or 0) for r in rows]


async def run_step1(
    db: AsyncSession,
    commodity_skus: list[str] | None,
    today: date,
) -> dict[str, dict[str, float]]:
    items = await load_velocity_inputs(db, commodity_skus=commodity_skus, today=today)
    return aggregate_velocity_from_items(items, today)
