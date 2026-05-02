"""Inventory SKU mapping helpers used by calculation steps."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.in_transit import InTransitItem, InTransitRecord
from app.models.inventory import InventorySnapshotLatest
from app.models.sku_mapping import SkuMappingRule
from app.models.warehouse import Warehouse


@dataclass(frozen=True, slots=True)
class MappingComponent:
    inventory_sku: str
    quantity: int


MappingGroup = list[MappingComponent]
MappingRules = dict[str, list[MappingGroup]]


@dataclass(frozen=True, slots=True)
class WarehouseStock:
    country: str | None
    total: int


async def load_active_mapping_rules(
    db: AsyncSession,
    commodity_skus: list[str] | None,
) -> MappingRules:
    stmt = (
        select(SkuMappingRule)
        .options(selectinload(SkuMappingRule.components))
        .where(SkuMappingRule.enabled.is_(True))
        .order_by(SkuMappingRule.commodity_sku)
    )
    if commodity_skus is not None:
        stmt = stmt.where(SkuMappingRule.commodity_sku.in_(commodity_skus))
    rows = (await db.execute(stmt)).scalars().all()
    rules: MappingRules = {}
    for row in rows:
        groups: dict[int, MappingGroup] = defaultdict(list)
        for component in row.components:
            groups[component.group_no].append(
                MappingComponent(
                    inventory_sku=component.inventory_sku,
                    quantity=component.quantity,
                )
            )
        if groups:
            rules[row.commodity_sku] = [groups[group_no] for group_no in sorted(groups)]
    return rules


def component_skus_for_rules(rules: MappingRules) -> list[str]:
    return sorted(
        {
            component.inventory_sku
            for groups in rules.values()
            for components in groups
            for component in components
        }
    )


async def load_inventory_totals_by_warehouse(
    db: AsyncSession,
    inventory_skus: list[str],
    *,
    warehouse_type: int | None = None,
    exclude_warehouse_type: int | None = None,
) -> dict[tuple[str, str], WarehouseStock]:
    if not inventory_skus:
        return {}
    stmt = (
        select(
            InventorySnapshotLatest.commodity_sku,
            InventorySnapshotLatest.warehouse_id,
            InventorySnapshotLatest.country,
            func.sum(InventorySnapshotLatest.available + InventorySnapshotLatest.reserved).label(
                "total"
            ),
        )
        .join(Warehouse, Warehouse.id == InventorySnapshotLatest.warehouse_id)
        .where(InventorySnapshotLatest.commodity_sku.in_(inventory_skus))
        .group_by(
            InventorySnapshotLatest.commodity_sku,
            InventorySnapshotLatest.warehouse_id,
            InventorySnapshotLatest.country,
        )
    )
    if warehouse_type is not None:
        stmt = stmt.where(Warehouse.type == warehouse_type)
    if exclude_warehouse_type is not None:
        stmt = stmt.where(Warehouse.type != exclude_warehouse_type)
    rows = (await db.execute(stmt)).all()
    return {
        (sku, warehouse_id): WarehouseStock(country=country, total=int(total or 0))
        for sku, warehouse_id, country, total in rows
    }


async def load_in_transit_totals_by_warehouse(
    db: AsyncSession,
    inventory_skus: list[str],
    *,
    warehouse_type: int | None = None,
    exclude_warehouse_type: int | None = None,
) -> dict[tuple[str, str], WarehouseStock]:
    """Load component in-transit quantities that have target warehouse IDs."""
    if not inventory_skus:
        return {}
    stmt = (
        select(
            InTransitItem.commodity_sku,
            InTransitRecord.target_warehouse_id,
            InTransitRecord.target_country,
            func.sum(InTransitItem.goods).label("goods_total"),
        )
        .join(
            InTransitRecord,
            InTransitRecord.saihu_out_record_id == InTransitItem.saihu_out_record_id,
        )
        .join(Warehouse, Warehouse.id == InTransitRecord.target_warehouse_id)
        .where(InTransitRecord.is_in_transit.is_(True))
        .where(InTransitRecord.target_warehouse_id.is_not(None))
        .where(InTransitRecord.target_country.is_not(None))
        .where(InTransitItem.commodity_sku.in_(inventory_skus))
        .group_by(
            InTransitItem.commodity_sku,
            InTransitRecord.target_warehouse_id,
            InTransitRecord.target_country,
        )
    )
    if warehouse_type is not None:
        stmt = stmt.where(Warehouse.type == warehouse_type)
    if exclude_warehouse_type is not None:
        stmt = stmt.where(Warehouse.type != exclude_warehouse_type)
    rows = (await db.execute(stmt)).all()
    return {
        (sku, warehouse_id): WarehouseStock(country=country, total=int(total or 0))
        for sku, warehouse_id, country, total in rows
    }


def merge_warehouse_stock(
    *stock_maps: dict[tuple[str, str], WarehouseStock],
) -> dict[tuple[str, str], WarehouseStock]:
    merged: dict[tuple[str, str], WarehouseStock] = {}
    for stock_map in stock_maps:
        for key, stock in stock_map.items():
            current = merged.get(key)
            if current is None:
                merged[key] = stock
                continue
            merged[key] = WarehouseStock(country=current.country or stock.country, total=current.total + stock.total)
    return merged


def compute_mapped_stock_by_country(
    rules: MappingRules,
    component_stock: dict[tuple[str, str], WarehouseStock],
) -> dict[tuple[str, str], int]:
    """Return assembled commodity stock aggregated by ``(commodity_sku, country)``."""
    result: defaultdict[tuple[str, str], int] = defaultdict(int)
    if not rules or not component_stock:
        return {}

    warehouse_ids = {warehouse_id for _, warehouse_id in component_stock}
    for commodity_sku, groups in rules.items():
        for warehouse_id in warehouse_ids:
            for components in groups:
                country: str | None = None
                buildable: int | None = None
                for component in components:
                    stock = component_stock.get((component.inventory_sku, warehouse_id))
                    if stock is None:
                        buildable = 0
                        break
                    country = country or stock.country
                    buildable_for_component = stock.total // component.quantity
                    buildable = (
                        buildable_for_component
                        if buildable is None
                        else min(buildable, buildable_for_component)
                    )
                if country and buildable and buildable > 0:
                    result[(commodity_sku, country)] += buildable
    return dict(result)


def compute_mapped_stock_total_by_sku(
    rules: MappingRules,
    component_stock: dict[tuple[str, str], WarehouseStock],
) -> dict[str, int]:
    """Return assembled local stock aggregated by commodity SKU."""
    totals: defaultdict[str, int] = defaultdict(int)
    if not rules or not component_stock:
        return {}

    warehouse_ids = {warehouse_id for _, warehouse_id in component_stock}
    for commodity_sku, groups in rules.items():
        for warehouse_id in warehouse_ids:
            for components in groups:
                buildable: int | None = None
                for component in components:
                    stock = component_stock.get((component.inventory_sku, warehouse_id))
                    if stock is None:
                        buildable = 0
                        break
                    buildable_for_component = stock.total // component.quantity
                    buildable = (
                        buildable_for_component
                        if buildable is None
                        else min(buildable, buildable_for_component)
                    )
                if buildable and buildable > 0:
                    totals[commodity_sku] += buildable
    return dict(totals)
