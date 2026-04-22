"""Step 2: sale_days from overseas stock.

Formula (FR-030):
    sale_days[country] = (available + reserved + in_transit) / velocity[country]

Current business rule:
- available + reserved still come from overseas warehouse inventory
- in_transit comes from synced active out-records aggregated by ``(sku, country)``
"""

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.context import InventoryStock
from app.models.in_transit import InTransitItem, InTransitRecord
from app.models.inventory import InventorySnapshotLatest
from app.models.warehouse import Warehouse


async def load_oversea_inventory(
    db: AsyncSession,
    commodity_skus: list[str] | None,
) -> dict[tuple[str, str], dict[str, int]]:
    """Load overseas inventory aggregated by ``(sku, country)``."""
    stmt = (
        select(
            InventorySnapshotLatest.commodity_sku,
            InventorySnapshotLatest.country,
            func.sum(InventorySnapshotLatest.available).label("avail"),
            func.sum(InventorySnapshotLatest.reserved).label("reserv"),
        )
        .join(Warehouse, Warehouse.id == InventorySnapshotLatest.warehouse_id)
        .where(Warehouse.type != 1)
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
    """Load in-transit quantities from synced active out-record tables."""
    stmt = (
        select(
            InTransitItem.commodity_sku,
            InTransitRecord.target_country,
            func.sum(InTransitItem.goods).label("goods_total"),
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

    return {(sku, country): int(goods_total or 0) for sku, country, goods_total in rows}


def merge_inventory(
    oversea: dict[tuple[str, str], dict[str, int]],
    in_transit: dict[tuple[str, str], int],
) -> dict[str, dict[str, InventoryStock]]:
    """Merge overseas stock and in-transit stock into one structure.

    Returns: ``{sku: {country: InventoryStock}}``
    """
    merged: defaultdict[str, dict[str, InventoryStock]] = defaultdict(dict)
    keys = set(oversea.keys()) | set(in_transit.keys())
    for sku, country in keys:
        inv = oversea.get((sku, country), {"available": 0, "reserved": 0})
        transit = in_transit.get((sku, country), 0)
        merged[sku][country] = InventoryStock(
            available=int(inv["available"]),
            reserved=int(inv["reserved"]),
            in_transit=int(transit),
        )
    return dict(merged)


def compute_sale_days(
    velocity: dict[str, dict[str, float]],
    inventory: dict[str, dict[str, InventoryStock]],
) -> dict[str, dict[str, float]]:
    """Compute ``sale_days`` for each ``(sku, country)`` with positive velocity."""
    result: defaultdict[str, dict[str, float]] = defaultdict(dict)
    for sku, country_map in velocity.items():
        for country, v in country_map.items():
            if v <= 0:
                continue
            stock = inventory.get(sku, {}).get(country)
            result[sku][country] = (stock.total if stock is not None else 0) / v
    return dict(result)


async def run_step2(
    db: AsyncSession,
    velocity: dict[str, dict[str, float]],
    commodity_skus: list[str] | None,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, InventoryStock]]]:
    oversea = await load_oversea_inventory(db, commodity_skus)
    in_transit = await load_in_transit(db, commodity_skus)
    inventory = merge_inventory(oversea, in_transit)
    sale_days = compute_sale_days(velocity, inventory)
    return sale_days, inventory
