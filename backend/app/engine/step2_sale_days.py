"""Step 2: sale_days from overseas stock.

Formula (FR-030):
    sale_days[country] = (available + reserved + in_transit) / velocity[country]

Current business rule:
- available + reserved come from current overseas inventory maintained in the UI
- in_transit comes from synced active out-records aggregated by ``(sku, country)``
"""

from collections import defaultdict

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.countries import is_reportable_country_code
from app.core.country_mapping import apply_eu_mapping, load_eu_countries
from app.engine.context import InventoryMap, InventoryStock, SaleDaysMap, VelocityMap
from app.engine.sku_mapping import (
    WarehouseStock,
    aggregate_component_stock_by_country,
    component_skus_for_rules,
    compute_mapped_stock_by_country,
    load_active_mapping_rules,
    load_in_transit_totals_by_country,
    load_in_transit_totals_by_warehouse,
    merge_warehouse_stock,
)
from app.engine.warehouse_scope import LOCAL_WAREHOUSE_TYPES
from app.models.in_transit import InTransitItem, InTransitRecord
from app.models.third_party_inventory import ThirdPartyInventoryCurrent, ThirdPartyWarehouse
from app.models.warehouse import Warehouse

THIRD_PARTY_WAREHOUSE_KEY_PREFIX = "third_party"


async def load_third_party_inventory(
    db: AsyncSession,
    commodity_skus: list[str] | None,
    *,
    eu_countries: set[str] | None = None,
) -> dict[tuple[str, str], dict[str, int]]:
    """Load current third-party inventory aggregated by ``(sku, country)``."""
    stmt = (
        select(
            ThirdPartyInventoryCurrent.commodity_sku,
            ThirdPartyWarehouse.country,
            func.sum(ThirdPartyInventoryCurrent.available).label("avail"),
            func.sum(ThirdPartyInventoryCurrent.reserved).label("reserv"),
        )
        .join(
            ThirdPartyWarehouse, ThirdPartyWarehouse.id == ThirdPartyInventoryCurrent.warehouse_id
        )
        .where(ThirdPartyWarehouse.country.is_not(None))
        .group_by(ThirdPartyInventoryCurrent.commodity_sku, ThirdPartyWarehouse.country)
    )
    if commodity_skus is not None:
        stmt = stmt.where(ThirdPartyInventoryCurrent.commodity_sku.in_(commodity_skus))
    rows = (await db.execute(stmt)).all()
    result: dict[tuple[str, str], dict[str, int]] = {}
    for sku, country, avail, reserv in rows:
        mapped_country = apply_eu_mapping(country, eu_countries or set())
        if mapped_country is None or not is_reportable_country_code(mapped_country):
            continue
        current = result.setdefault((sku, mapped_country), {"available": 0, "reserved": 0})
        current["available"] += int(avail or 0)
        current["reserved"] += int(reserv or 0)
    return result


def _third_party_warehouse_key(warehouse_id: int) -> str:
    return f"{THIRD_PARTY_WAREHOUSE_KEY_PREFIX}:{warehouse_id}"


async def load_third_party_component_inventory_by_warehouse(
    db: AsyncSession,
    inventory_skus: list[str],
    *,
    sku_to_group_key: dict[str, str] | None = None,
    eu_countries: set[str] | None = None,
) -> dict[tuple[str, str], WarehouseStock]:
    """Load current third-party component inventory by overseas warehouse.

    The synthetic warehouse key is prefixed so manual third-party warehouse IDs
    cannot collide with Saihu warehouse IDs used by in-transit records.
    """
    if not inventory_skus:
        return {}
    stmt = (
        select(
            ThirdPartyInventoryCurrent.commodity_sku,
            ThirdPartyInventoryCurrent.warehouse_id,
            ThirdPartyWarehouse.country,
            func.sum(
                ThirdPartyInventoryCurrent.available + ThirdPartyInventoryCurrent.reserved
            ).label("total"),
        )
        .join(
            ThirdPartyWarehouse, ThirdPartyWarehouse.id == ThirdPartyInventoryCurrent.warehouse_id
        )
        .where(ThirdPartyWarehouse.country.is_not(None))
        .where(ThirdPartyInventoryCurrent.commodity_sku.in_(inventory_skus))
        .group_by(
            ThirdPartyInventoryCurrent.commodity_sku,
            ThirdPartyInventoryCurrent.warehouse_id,
            ThirdPartyWarehouse.country,
        )
    )
    rows = (await db.execute(stmt)).all()
    sku_groups = sku_to_group_key or {}
    result: dict[tuple[str, str], WarehouseStock] = {}
    for sku, warehouse_id, country, total in rows:
        mapped_country = apply_eu_mapping(country, eu_countries or set())
        if mapped_country is None or not is_reportable_country_code(mapped_country):
            continue
        key = (sku_groups.get(sku, sku), _third_party_warehouse_key(int(warehouse_id)))
        current = result.get(key)
        if current is None:
            result[key] = WarehouseStock(country=mapped_country, total=int(total or 0))
        else:
            result[key] = WarehouseStock(
                country=current.country or mapped_country,
                total=current.total + int(total or 0),
            )
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
        .outerjoin(Warehouse, Warehouse.id == InTransitRecord.target_warehouse_id)
        .where(InTransitRecord.is_in_transit.is_(True))
        .where(InTransitRecord.target_country.is_not(None))
        .where(
            or_(
                InTransitRecord.target_warehouse_id.is_(None),
                ~Warehouse.type.in_(LOCAL_WAREHOUSE_TYPES),
            )
        )
        .group_by(InTransitItem.commodity_sku, InTransitRecord.target_country)
    )
    if commodity_skus is not None:
        stmt = stmt.where(InTransitItem.commodity_sku.in_(commodity_skus))

    rows = (await db.execute(stmt)).all()

    result: defaultdict[tuple[str, str], int] = defaultdict(int)
    for sku, country, goods_total in rows:
        if not is_reportable_country_code(country):
            continue
        result[(sku, country)] += int(goods_total or 0)
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
            if not is_reportable_country_code(country):
                continue
            if v <= 0:
                continue
            stock = inventory.get(sku, {}).get(country)
            if stock is None:
                continue
            result[sku][country] = stock.total / v
    return dict(result)


async def run_step2(
    db: AsyncSession,
    velocity: VelocityMap,
    commodity_skus: list[str] | None,
    sku_to_group_key: dict[str, str] | None = None,
    members_by_group_key: dict[str, list[str]] | None = None,
) -> tuple[SaleDaysMap, InventoryMap]:
    eu_countries = await load_eu_countries(db)
    oversea = await load_third_party_inventory(
        db,
        commodity_skus,
        eu_countries=eu_countries,
    )
    in_transit = await load_in_transit(db, commodity_skus)
    rules = await load_active_mapping_rules(db, commodity_skus, sku_to_group_key=sku_to_group_key)
    component_skus = component_skus_for_rules(rules)
    if component_skus:
        component_query_skus = sorted(
            {
                source_sku
                for component_sku in component_skus
                for source_sku in (
                    members_by_group_key.get(component_sku, [component_sku])
                    if members_by_group_key is not None
                    else [component_sku]
                )
            }
        )
        component_third_party_inventory = await load_third_party_component_inventory_by_warehouse(
            db,
            component_query_skus,
            sku_to_group_key=sku_to_group_key,
            eu_countries=eu_countries,
        )
        component_transit = await load_in_transit_totals_by_warehouse(
            db,
            component_query_skus,
            exclude_warehouse_types=LOCAL_WAREHOUSE_TYPES,
            sku_to_group_key=sku_to_group_key,
        )
        component_country_transit = await load_in_transit_totals_by_country(
            db,
            component_query_skus,
            sku_to_group_key=sku_to_group_key,
        )
        warehouse_component_stock = merge_warehouse_stock(
            component_third_party_inventory,
            component_transit,
        )
        mapped = compute_mapped_stock_by_country(
            rules,
            warehouse_component_stock,
            velocity=velocity,
        )
        if component_country_transit:
            country_component_stock = aggregate_component_stock_by_country(
                warehouse_component_stock,
                component_country_transit,
            )
            country_mapped = compute_mapped_stock_by_country(
                rules,
                country_component_stock,
                velocity=velocity,
            )
            country_level_countries = {country for _, country in component_country_transit}
            mapped = {
                key: quantity
                for key, quantity in mapped.items()
                if key[1] not in country_level_countries
            }
            for key, quantity in country_mapped.items():
                if key[1] in country_level_countries:
                    mapped[key] = quantity
        for key, quantity in mapped.items():
            current = oversea.setdefault(key, {"available": 0, "reserved": 0})
            current["available"] += quantity
    inventory = merge_inventory(oversea, in_transit)
    sale_days = compute_sale_days(velocity, inventory)
    return sale_days, inventory
