"""Step 5:各国仓内分配(简化版 FR-033 + analyze G6)。

策略:
- 取该 SKU 在该国近 30 天非已作废包裹订单,优先使用订单头邮编,无邮编也参与未知样本
- 按 zipcode_rule 分配到具体仓 -> 未匹配的归"未知仓"
- 已知与未知同时存在时,先按样本件数拆成已知桶和未知桶
- 已知桶按真实比例分配,未知桶均分到该国已配置邮编规则的仓
- 已知仓总件数 = 0:均分到该国所有已配置邮编规则的仓(零数据兜底)
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from fractions import Fraction

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import BEIJING
from app.engine.zipcode_matcher import ZipcodeRule, match_warehouses
from app.models.order import ORDER_SOURCE_PACKAGE, OrderHeader, OrderItem
from app.models.warehouse import Warehouse
from app.models.zipcode_rule import ZipcodeRule as ZipcodeRuleModel

WINDOW_DAYS = 30
CANCELED_PACKAGE_STATUS = "has_canceled"


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
    sku_alias_map: dict[str, str] | None = None,
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
        # Step 5 uses the same effective quantity and package status scope as Step 1.
        select(
            OrderItem.commodity_sku,
            OrderHeader.country_code,
            OrderHeader.postal_code,
            (OrderItem.quantity_shipped - OrderItem.refund_num).label("effective_qty"),
        )
        .join(OrderHeader, OrderHeader.id == OrderItem.order_id)
        .where(OrderItem.commodity_sku.in_(commodity_skus))
        .where(OrderHeader.purchase_date >= earliest_dt)
        .where(OrderHeader.purchase_date < end_dt)
        .where(OrderHeader.source == ORDER_SOURCE_PACKAGE)
        .where(func.coalesce(OrderHeader.package_status, "") != CANCELED_PACKAGE_STATUS)
    )
    if allowed_countries is not None:
        stmt = stmt.where(OrderHeader.country_code.in_(sorted(allowed_countries)))
    rows = (await db.execute(stmt)).all()

    grouped: dict[tuple[str, str], list[tuple[str | None, int]]] = {}
    aliases = sku_alias_map or {}
    for sku, country, postal, qty in rows:
        effective_qty = max(int(qty or 0), 0)
        if effective_qty <= 0:
            continue
        key = (aliases.get(sku, sku), country)
        grouped.setdefault(key, []).append((postal, effective_qty))
    return grouped


def _allocate_by_weights(
    total_qty: int,
    ordered_weights: list[tuple[str, Fraction]],
) -> dict[str, int]:
    """按权重分配整数数量,使用 floor + 最大余数法保证总和精确。"""
    if total_qty <= 0 or not ordered_weights:
        return {}

    total_weight = sum(weight for _, weight in ordered_weights)
    if total_weight <= 0:
        return {}

    result: dict[str, int] = {}
    remainders: list[tuple[Fraction, int, str]] = []
    allocated = 0
    for order_index, (key, weight) in enumerate(ordered_weights):
        exact = Fraction(total_qty) * weight / total_weight
        base = exact.numerator // exact.denominator
        result[key] = base
        allocated += base
        remainders.append((exact - base, order_index, key))

    for _, _, key in sorted(remainders, key=lambda item: (-item[0], item[1]))[
        : total_qty - allocated
    ]:
        result[key] += 1

    return {key: qty for key, qty in result.items() if qty > 0}


def _allocate_even(total_qty: int, warehouses: list[str]) -> dict[str, int]:
    if total_qty <= 0 or not warehouses:
        return {}

    base = total_qty // len(warehouses)
    remainder = total_qty - base * len(warehouses)
    return {
        wid: qty
        for i, wid in enumerate(warehouses)
        if (qty := base + (1 if i < remainder else 0)) > 0
    }


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
    known_counts: defaultdict[str, Fraction] = defaultdict(Fraction)
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
        share = Fraction(qty, len(eligible_winners))
        for wid in eligible_winners:
            known_counts[wid] += share
        matched_order_qty += qty

    total_known = sum(known_counts.values())

    if total_known > 0:
        # 已知桶按真实比例分配；未知桶按规则仓均分,再合并两部分。
        bucket_allocations = _allocate_by_weights(
            country_qty,
            [
                ("known", Fraction(matched_order_qty)),
                ("unknown", Fraction(unknown_order_qty)),
            ],
        )
        known_qty = bucket_allocations.get("known", 0)
        unknown_qty = bucket_allocations.get("unknown", 0)

        ordered_counts = [
            (wid, known_counts[wid]) for wid in eligible_warehouses if wid in known_counts
        ]
        result = _allocate_by_weights(known_qty, ordered_counts)
        for wid, qty in _allocate_even(unknown_qty, eligible_warehouses).items():
            result[wid] = result.get(wid, 0) + qty

        return CountryAllocationResult(
            warehouse_breakdown={k: v for k, v in result.items() if v > 0},
            allocation_mode=("mixed_known_unknown" if unknown_order_qty > 0 else "matched"),
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
    result = _allocate_even(country_qty, eligible_warehouses)
    return CountryAllocationResult(
        warehouse_breakdown={k: v for k, v in result.items() if v > 0},
        allocation_mode="fallback_even",
        matched_order_qty=0,
        unknown_order_qty=unknown_order_qty,
        eligible_warehouses=eligible_warehouses,
    )
