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

from app.engine.context import InventoryMap, InventoryStock, SaleDaysMap, VelocityMap
from app.engine.sku_mapping import (
    component_skus_for_rules,
    compute_mapped_stock_by_country,
    load_active_mapping_rules,
    load_in_transit_totals_by_warehouse,
    load_inventory_totals_by_warehouse,
    merge_warehouse_stock,
)
from app.models.in_transit import InTransitItem, InTransitRecord
from app.models.inventory import InventorySnapshotLatest
from app.models.warehouse import Warehouse


async def load_oversea_inventory(
    db: AsyncSession,
    commodity_skus: list[str] | None,
    sku_alias_map: dict[str, str] | None = None,
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
    aliases = sku_alias_map or {}
    for sku, country, avail, reserv in rows:
        key = (aliases.get(sku, sku), country)
        current = result.setdefault(key, {"available": 0, "reserved": 0})
        current["available"] += int(avail or 0)
        current["reserved"] += int(reserv or 0)
    return result


async def load_in_transit(
    db: AsyncSession,
    commodity_skus: list[str] | None,
    sku_alias_map: dict[str, str] | None = None,
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

    aliases = sku_alias_map or {}
    result: defaultdict[tuple[str, str], int] = defaultdict(int)
    for sku, country, goods_total in rows:
        result[(aliases.get(sku, sku), country)] += int(goods_total or 0)
    return dict(result)


def merge_inventory(
    oversea: dict[tuple[str, str], dict[str, int]],
    in_transit: dict[tuple[str, str], int],
) -> InventoryMap:
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
    velocity: VelocityMap,
    inventory: InventoryMap,
) -> SaleDaysMap:
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
    velocity: VelocityMap,
    commodity_skus: list[str] | None,
    sku_alias_map: dict[str, str] | None = None,
    component_source_skus: dict[str, list[str]] | None = None,
) -> tuple[SaleDaysMap, InventoryMap]:
    oversea = await load_oversea_inventory(db, commodity_skus, sku_alias_map=sku_alias_map)
    in_transit = await load_in_transit(db, commodity_skus, sku_alias_map=sku_alias_map)
    rules = await load_active_mapping_rules(db, commodity_skus, sku_alias_map=sku_alias_map)
    component_skus = component_skus_for_rules(rules)
    if component_skus:
        component_query_skus = sorted(
            {
                source_sku
                for component_sku in component_skus
                for source_sku in (
                    component_source_skus.get(component_sku, [component_sku])
                    if component_source_skus is not None
                    else [component_sku]
                )
            }
        )
        component_inventory = await load_inventory_totals_by_warehouse(
            db,
            component_query_skus,
            exclude_warehouse_type=1,
            sku_alias_map=sku_alias_map,
        )
        component_transit = await load_in_transit_totals_by_warehouse(
            db,
            component_query_skus,
            exclude_warehouse_type=1,
            sku_alias_map=sku_alias_map,
        )
        mapped = compute_mapped_stock_by_country(
            rules,
            merge_warehouse_stock(component_inventory, component_transit),
            velocity=velocity,
        )
        for key, quantity in mapped.items():
            current = oversea.setdefault(key, {"available": 0, "reserved": 0})
            current["available"] += quantity
    inventory = merge_inventory(oversea, in_transit)
    sale_days = compute_sale_days(velocity, inventory)
    return sale_days, inventory
