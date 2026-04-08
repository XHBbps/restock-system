"""Step 2：各国销售天数。

公式（FR-030）：
    sale_days[国] = (海外仓 available + reserved + in_transit) / velocity[国]

数据源：
- available + reserved 来自 inventory_snapshot_latest（按 country 聚合 type ≠ 1 的仓）
- in_transit 来自 in_transit_item JOIN in_transit_record (is_in_transit=true)
"""

from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.in_transit import InTransitItem, InTransitRecord
from app.models.inventory import InventorySnapshotLatest
from app.models.warehouse import Warehouse


async def load_oversea_inventory(
    db: AsyncSession,
    commodity_skus: list[str] | None,
) -> dict[tuple[str, str], dict[str, int]]:
    """加载海外仓库存（按 sku × country 聚合 available/reserved）。

    返回：{(sku, country): {available, reserved}}
    """
    stmt = (
        select(
            InventorySnapshotLatest.commodity_sku,
            InventorySnapshotLatest.country,
            func.sum(InventorySnapshotLatest.available).label("avail"),
            func.sum(InventorySnapshotLatest.reserved).label("reserv"),
        )
        .join(Warehouse, Warehouse.id == InventorySnapshotLatest.warehouse_id)
        .where(Warehouse.type != 1)  # 非国内仓
        .where(InventorySnapshotLatest.country.is_not(None))
        .group_by(InventorySnapshotLatest.commodity_sku, InventorySnapshotLatest.country)
    )
    if commodity_skus is not None:
        stmt = stmt.where(InventorySnapshotLatest.commodity_sku.in_(commodity_skus))
    rows = (await db.execute(stmt)).all()
    result: dict[tuple[str, str], dict[str, int]] = {}
    for sku, country, avail, reserv in rows:
        result[(sku, country)] = {
            "available": int(avail or 0),
            "reserved": int(reserv or 0),
        }
    return result


async def load_in_transit(
    db: AsyncSession,
    commodity_skus: list[str] | None,
) -> dict[tuple[str, str], int]:
    """加载在途数据（按 sku × target_country 聚合）。

    返回：{(sku, country): in_transit_qty}
    """
    stmt = (
        select(
            InTransitItem.commodity_sku,
            InTransitRecord.target_country,
            func.sum(InTransitItem.goods).label("in_transit"),
        )
        .join(
            InTransitRecord,
            InTransitRecord.saihu_out_record_id == InTransitItem.saihu_out_record_id,
        )
        .where(InTransitRecord.is_in_transit.is_(True))
        .where(InTransitRecord.target_country.is_not(None))
        .group_by(InTransitItem.commodity_sku, InTransitRecord.target_country)
    )
    if commodity_skus is not None:
        stmt = stmt.where(InTransitItem.commodity_sku.in_(commodity_skus))
    rows = (await db.execute(stmt)).all()
    return {(sku, country): int(qty or 0) for sku, country, qty in rows}


def merge_inventory(
    oversea: dict[tuple[str, str], dict[str, int]],
    in_transit: dict[tuple[str, str], int],
) -> dict[str, dict[str, dict[str, int]]]:
    """合并海外仓库存与在途为统一结构。

    返回：{sku: {country: {available, reserved, in_transit, total}}}
    """
    merged: defaultdict[str, dict[str, dict[str, int]]] = defaultdict(dict)
    keys = set(oversea.keys()) | set(in_transit.keys())
    for sku, country in keys:
        inv = oversea.get((sku, country), {"available": 0, "reserved": 0})
        transit = in_transit.get((sku, country), 0)
        total = inv["available"] + inv["reserved"] + transit
        merged[sku][country] = {
            "available": inv["available"],
            "reserved": inv["reserved"],
            "in_transit": transit,
            "total": total,
        }
    return dict(merged)


def compute_sale_days(
    velocity: dict[str, dict[str, float]],
    inventory: dict[str, dict[str, dict[str, int]]],
) -> dict[str, dict[str, float]]:
    """对每个 (sku, country) 算 sale_days。"""
    result: defaultdict[str, dict[str, float]] = defaultdict(dict)
    for sku, country_map in velocity.items():
        for country, v in country_map.items():
            if v <= 0:
                continue
            stock = inventory.get(sku, {}).get(country, {}).get("total", 0)
            result[sku][country] = stock / v
    return dict(result)


async def run_step2(
    db: AsyncSession,
    velocity: dict[str, dict[str, float]],
    commodity_skus: list[str] | None,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, dict[str, int]]]]:
    oversea = await load_oversea_inventory(db, commodity_skus)
    in_transit = await load_in_transit(db, commodity_skus)
    inventory = merge_inventory(oversea, in_transit)
    sale_days = compute_sale_days(velocity, inventory)
    return sale_days, inventory
