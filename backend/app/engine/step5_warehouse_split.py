"""Step 5：各国仓内分配（简化版 FR-033 + analyze G6）。

策略：
- 取该 SKU 在该国近 30 天已拉详情且有 postal_code 的订单
- 按 zipcode_rule 分配到具体仓 → 未匹配的归"未知仓"
- 已知仓总件数 > 0：按真实比例分配（不设阈值，不做小占比归零）
- 已知仓总件数 = 0：均分到该国所有"已维护国家"的海外仓（零数据兜底）
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import BEIJING
from app.engine.zipcode_matcher import ZipcodeRule, match_warehouse
from app.models.order import OrderDetail, OrderHeader, OrderItem
from app.models.warehouse import Warehouse
from app.models.zipcode_rule import ZipcodeRule as ZipcodeRuleModel

WINDOW_DAYS = 30


async def load_country_warehouses(
    db: AsyncSession,
) -> dict[str, list[str]]:
    """加载每个国家的可用海外仓 id（type ≠ 1 且已指定 country）。"""
    rows = (
        await db.execute(
            select(Warehouse.id, Warehouse.country)
            .where(Warehouse.type != 1)
            .where(Warehouse.country.is_not(None))
            .order_by(Warehouse.country, Warehouse.id)
        )
    ).all()
    result: defaultdict[str, list[str]] = defaultdict(list)
    for wid, country in rows:
        result[country].append(wid)
    return dict(result)


async def load_zipcode_rules(db: AsyncSession) -> list[ZipcodeRule]:
    """加载所有邮编规则并转为简化数据结构。"""
    rows = (await db.execute(select(ZipcodeRuleModel))).scalars().all()
    return [
        ZipcodeRule(
            id=r.id,
            country=r.country,
            prefix_length=r.prefix_length,
            value_type=r.value_type,
            operator=r.operator,
            compare_value=r.compare_value,
            warehouse_id=r.warehouse_id,
            priority=r.priority,
        )
        for r in rows
    ]


async def load_sku_country_orders(
    db: AsyncSession,
    sku: str,
    country: str,
    today: date,
) -> list[tuple[str | None, int]]:
    """加载该 SKU 在该国近 30 天的订单（postal_code, qty_shipped）。

    仅返回有 order_detail 的订单。
    """
    earliest_dt = datetime.combine(
        today - timedelta(days=WINDOW_DAYS), datetime.min.time(), tzinfo=BEIJING
    )
    end_dt = datetime.combine(today, datetime.min.time(), tzinfo=BEIJING)

    stmt = (
        select(OrderDetail.postal_code, OrderItem.quantity_shipped)
        .join(OrderHeader, OrderHeader.id == OrderItem.order_id)
        .join(
            OrderDetail,
            (OrderDetail.shop_id == OrderHeader.shop_id)
            & (OrderDetail.amazon_order_id == OrderHeader.amazon_order_id),
        )
        .where(OrderItem.commodity_sku == sku)
        .where(OrderHeader.country_code == country)
        .where(OrderHeader.purchase_date >= earliest_dt)
        .where(OrderHeader.purchase_date < end_dt)
        .where(OrderHeader.order_status.in_(("Shipped", "PartiallyShipped")))
    )
    rows = (await db.execute(stmt)).all()
    return [(r[0], int(r[1] or 0)) for r in rows]


def split_country_qty(
    *,
    sku: str,
    country: str,
    country_qty: int,
    orders: list[tuple[str | None, int]],
    rules: list[ZipcodeRule],
    country_warehouses: list[str],
) -> dict[str, int]:
    """把 country_qty 分配到该国的各个仓。

    orders: [(postal_code, qty_shipped), ...]
    返回：{warehouse_id: qty}
    """
    if country_qty <= 0:
        return {}

    # 已知仓件数统计
    known_counts: defaultdict[str, int] = defaultdict(int)
    for postal_code, qty in orders:
        wid = match_warehouse(postal_code, country, rules)
        if wid is None:
            continue
        known_counts[wid] += qty

    total_known = sum(known_counts.values())

    if total_known > 0:
        # 按真实比例分配
        result: dict[str, int] = {}
        accumulated = 0
        items = list(known_counts.items())
        for i, (wid, cnt) in enumerate(items):
            if i == len(items) - 1:
                # 最后一仓兜底，避免四舍五入误差
                result[wid] = country_qty - accumulated
            else:
                share = int(round(country_qty * cnt / total_known))
                result[wid] = share
                accumulated += share
        # 清理 0 值
        return {k: v for k, v in result.items() if v > 0}

    # 零数据兜底：均分给该国所有已维护海外仓
    if not country_warehouses:
        return {}
    base = country_qty // len(country_warehouses)
    remainder = country_qty - base * len(country_warehouses)
    result = {}
    for i, wid in enumerate(country_warehouses):
        result[wid] = base + (1 if i < remainder else 0)
    return {k: v for k, v in result.items() if v > 0}
