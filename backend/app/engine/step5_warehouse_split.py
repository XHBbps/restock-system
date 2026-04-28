"""Step 5:各国仓内分配(简化版 FR-033 + analyze G6)。

策略:
- 取该 SKU 在该国近 30 天已拉详情且有 postal_code 的订单
- 按 zipcode_rule 分配到具体仓 -> 未匹配的归"未知仓"
- 已知仓总件数 > 0:按真实比例分配(不设阈值,不做小占比归零)
- 已知仓总件数 = 0:均分到该国所有"已维护国家"的海外仓(零数据兜底)
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import BEIJING
from app.engine.zipcode_matcher import ZipcodeRule, match_warehouses
from app.models.order import OrderDetail, OrderHeader, OrderItem
from app.models.warehouse import Warehouse
from app.models.zipcode_rule import ZipcodeRule as ZipcodeRuleModel

WINDOW_DAYS = 30


@dataclass
class CountryAllocationResult:
    warehouse_breakdown: dict[str, int]
    allocation_mode: str
    matched_order_qty: int
    unknown_order_qty: int
    eligible_warehouses: list[str]


async def load_country_warehouses(
    db: AsyncSession,
) -> dict[str, list[str]]:
    """加载每个国家可参与 Step 5 的规则仓。

    只有同时满足以下条件的仓才参与分仓：
    - 海外仓（`type != 1`）
    - 仓库已配置国家
    - 该国家下至少存在一条邮编规则指向该仓
    """
    rows = (
        await db.execute(
            select(ZipcodeRuleModel.country, ZipcodeRuleModel.warehouse_id)
            .join(Warehouse, Warehouse.id == ZipcodeRuleModel.warehouse_id)
            .where(Warehouse.type != 1)
            .where(Warehouse.country.is_not(None))
            .where(Warehouse.country == ZipcodeRuleModel.country)
            .distinct()
            .order_by(ZipcodeRuleModel.country, ZipcodeRuleModel.warehouse_id)
        )
    ).all()
    result: defaultdict[str, list[str]] = defaultdict(list)
    for country, wid in rows:
        if wid not in result[country]:
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


async def load_all_sku_country_orders(
    db: AsyncSession,
    commodity_skus: list[str],
    today: date,
    allowed_countries: set[str] | None = None,
) -> dict[tuple[str, str], list[tuple[str | None, int]]]:
    """批量加载所有指定 SKU 近 30 天订单,按 (sku, country) 分组返回。

    规则引擎 runner 用一次查询替代 NxM 次(N SKU x M 国家),
    符合宪法 V 原则"禁止 N+1"。
    """
    if not commodity_skus:
        return {}

    earliest_dt = datetime.combine(
        today - timedelta(days=WINDOW_DAYS), datetime.min.time(), tzinfo=BEIJING
    )
    end_dt = datetime.combine(today, datetime.min.time(), tzinfo=BEIJING)

    stmt = (
        select(
            OrderItem.commodity_sku,
            OrderHeader.country_code,
            OrderDetail.postal_code,
            OrderItem.quantity_shipped,
        )
        .join(OrderHeader, OrderHeader.id == OrderItem.order_id)
        .join(
            OrderDetail,
            (OrderDetail.shop_id == OrderHeader.shop_id)
            & (OrderDetail.amazon_order_id == OrderHeader.amazon_order_id)
            & (OrderDetail.source == OrderHeader.source),
        )
        .where(OrderItem.commodity_sku.in_(commodity_skus))
        .where(OrderHeader.purchase_date >= earliest_dt)
        .where(OrderHeader.purchase_date < end_dt)
        .where(OrderHeader.order_status.in_(("Shipped", "PartiallyShipped")))
    )
    if allowed_countries is not None:
        stmt = stmt.where(OrderHeader.country_code.in_(sorted(allowed_countries)))
    rows = (await db.execute(stmt)).all()

    grouped: dict[tuple[str, str], list[tuple[str | None, int]]] = {}
    for sku, country, postal, qty in rows:
        key = (sku, country)
        grouped.setdefault(key, []).append((postal, int(qty or 0)))
    return grouped


def split_country_qty(
    *,
    sku: str,
    country: str,
    country_qty: int,
    orders: list[tuple[str | None, int]],
    rules: list[ZipcodeRule],
    country_warehouses: list[str],
) -> dict[str, int]:
    return explain_country_qty_split(
        sku=sku,
        country=country,
        country_qty=country_qty,
        orders=orders,
        rules=rules,
        country_warehouses=country_warehouses,
    ).warehouse_breakdown


def explain_country_qty_split(
    *,
    sku: str,
    country: str,
    country_qty: int,
    orders: list[tuple[str | None, int]],
    rules: list[ZipcodeRule],
    country_warehouses: list[str],
) -> CountryAllocationResult:
    """把 country_qty 分配到该国的各个仓。

    orders: [(postal_code, qty_shipped), ...]
    返回结构化结果,同时携带解释快照。
    """
    del sku  # 当前仅用于签名对齐 runner/测试调用
    if country_qty <= 0:
        return CountryAllocationResult(
            warehouse_breakdown={},
            allocation_mode="zero_qty",
            matched_order_qty=0,
            unknown_order_qty=0,
            eligible_warehouses=list(dict.fromkeys(country_warehouses)),
        )

    eligible_warehouses = list(dict.fromkeys(country_warehouses))
    eligible_set = set(eligible_warehouses)

    # 已知仓件数统计
    known_counts: defaultdict[str, float] = defaultdict(float)
    matched_order_qty = 0
    unknown_order_qty = 0
    for postal_code, qty in orders:
        if qty <= 0:
            continue
        winners = match_warehouses(postal_code, country, rules)
        eligible_winners = [w for w in winners if w in eligible_set]
        if not eligible_winners:
            unknown_order_qty += qty
            continue
        share = qty / len(eligible_winners)
        for wid in eligible_winners:
            known_counts[wid] += share
        matched_order_qty += qty

    total_known = sum(known_counts.values())

    if total_known > 0:
        # 按真实比例分配
        result: dict[str, int] = {}
        accumulated = 0
        items = list(known_counts.items())
        for i, (wid, cnt) in enumerate(items):
            if i == len(items) - 1:
                # 最后一仓兜底,吸收所有取整误差
                result[wid] = country_qty - accumulated
            else:
                share = round(country_qty * cnt / total_known)
                result[wid] = share
                accumulated += share
        # 清理 0 值
        return CountryAllocationResult(
            warehouse_breakdown={k: v for k, v in result.items() if v > 0},
            allocation_mode="matched",
            matched_order_qty=matched_order_qty,
            unknown_order_qty=unknown_order_qty,
            eligible_warehouses=eligible_warehouses,
        )

    # 零数据兜底:仅在该国“已配置邮编规则”的仓之间均分
    if not eligible_warehouses:
        return CountryAllocationResult(
            warehouse_breakdown={},
            allocation_mode="no_warehouse",
            matched_order_qty=0,
            unknown_order_qty=unknown_order_qty,
            eligible_warehouses=[],
        )
    base = country_qty // len(eligible_warehouses)
    remainder = country_qty - base * len(eligible_warehouses)
    result = {}
    for i, wid in enumerate(eligible_warehouses):
        result[wid] = base + (1 if i < remainder else 0)
    return CountryAllocationResult(
        warehouse_breakdown={k: v for k, v in result.items() if v > 0},
        allocation_mode="fallback_even",
        matched_order_qty=0,
        unknown_order_qty=unknown_order_qty,
        eligible_warehouses=eligible_warehouses,
    )
