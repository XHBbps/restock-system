"""Inventory SKU mapping helpers used by calculation steps."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass
from math import floor

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.countries import is_reportable_country_code
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
ComponentConsumers = dict[str, list[str]]


@dataclass(frozen=True, slots=True)
class WarehouseStock:
    country: str | None
    total: int


def _type_filter_values(
    single_type: int | None,
    type_set: Collection[int] | None,
) -> tuple[int, ...]:
    values: list[int] = []
    if single_type is not None:
        values.append(single_type)
    if type_set is not None:
        values.extend(type_set)
    return tuple(dict.fromkeys(values))


def mapping_component_consumers(rules: MappingRules) -> ComponentConsumers:
    consumers: defaultdict[str, set[str]] = defaultdict(set)
    for commodity_sku, groups in rules.items():
        for components in groups:
            for component in components:
                consumers[component.inventory_sku].add(commodity_sku)
    return {
        inventory_sku: sorted(commodity_skus) for inventory_sku, commodity_skus in consumers.items()
    }


def _country_weights_by_sku(velocity: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    weights_by_country: defaultdict[str, dict[str, float]] = defaultdict(dict)
    for commodity_sku, country_map in velocity.items():
        for country, weight in country_map.items():
            weights_by_country[country][commodity_sku] = weight
    return dict(weights_by_country)


def _local_weights_by_sku(velocity: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    return {
        "": {
            commodity_sku: sum(country_map.values())
            for commodity_sku, country_map in velocity.items()
        }
    }


async def load_active_mapping_rules(
    db: AsyncSession,
    commodity_skus: list[str] | None,
    sku_to_group_key: dict[str, str] | None = None,
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
    sku_groups = sku_to_group_key or {}
    rules: MappingRules = {}
    for row in rows:
        groups: dict[int, MappingGroup] = defaultdict(list)
        for component in row.components:
            normalized_inventory_sku = sku_groups.get(
                component.inventory_sku, component.inventory_sku
            )
            existing_index = next(
                (
                    idx
                    for idx, existing in enumerate(groups[component.group_no])
                    if existing.inventory_sku == normalized_inventory_sku
                ),
                None,
            )
            normalized_component = MappingComponent(
                inventory_sku=normalized_inventory_sku,
                quantity=component.quantity,
            )
            if existing_index is None:
                groups[component.group_no].append(normalized_component)
            else:
                existing = groups[component.group_no][existing_index]
                groups[component.group_no][existing_index] = MappingComponent(
                    inventory_sku=existing.inventory_sku,
                    quantity=max(existing.quantity, component.quantity),
                )
        if groups:
            commodity_sku = row.commodity_sku
            existing_signatures = {
                tuple((component.inventory_sku, component.quantity) for component in group)
                for group in rules.get(commodity_sku, [])
            }
            for group_no in sorted(groups):
                group = sorted(groups[group_no], key=lambda item: item.inventory_sku)
                signature = tuple(
                    (component.inventory_sku, component.quantity) for component in group
                )
                if signature in existing_signatures:
                    continue
                rules.setdefault(commodity_sku, []).append(group)
                existing_signatures.add(signature)
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


def _allocate_integer_quantity(
    total: int,
    consumers: list[str],
    weights: dict[str, float],
) -> dict[str, int]:
    if total <= 0 or not consumers:
        return dict.fromkeys(consumers, 0)
    if len(consumers) == 1:
        return {consumers[0]: total}

    positive_weights = [weights.get(consumer, 0.0) for consumer in consumers]
    use_equal_split = any(weight <= 0 for weight in positive_weights)
    if use_equal_split:
        positive_weights = [1.0] * len(consumers)

    weight_sum = sum(positive_weights)
    if weight_sum <= 0:
        positive_weights = [1.0] * len(consumers)
        weight_sum = float(len(consumers))

    raw_shares = [total * weight / weight_sum for weight in positive_weights]
    allocated = [floor(share) for share in raw_shares]
    remainder = total - sum(allocated)
    if remainder > 0:
        fractional_order = sorted(
            range(len(consumers)),
            key=lambda idx: (-(raw_shares[idx] - allocated[idx]), consumers[idx]),
        )
        for idx in fractional_order[:remainder]:
            allocated[idx] += 1
    return {consumer: allocated[idx] for idx, consumer in enumerate(consumers)}


def _build_component_allocation(
    rules: MappingRules,
    component_stock: dict[tuple[str, str], WarehouseStock],
    weights_by_country: dict[str, dict[str, float]],
    *,
    fixed_weight_country: str | None = None,
) -> dict[tuple[str, str, str], WarehouseStock]:
    allocations: dict[tuple[str, str, str], WarehouseStock] = {}
    consumers_by_component = mapping_component_consumers(rules)
    for (component_sku, warehouse_id), stock in component_stock.items():
        consumers = consumers_by_component.get(component_sku)
        if not consumers:
            continue
        weight_country = (
            fixed_weight_country if fixed_weight_country is not None else stock.country or ""
        )
        country_weights = weights_by_country.get(weight_country, {})
        weights = {
            commodity_sku: country_weights.get(commodity_sku, 0.0) for commodity_sku in consumers
        }
        splits = _allocate_integer_quantity(stock.total, consumers, weights)
        for commodity_sku, quantity in splits.items():
            allocations[(commodity_sku, component_sku, warehouse_id)] = WarehouseStock(
                country=stock.country,
                total=quantity,
            )
    return allocations


async def load_inventory_totals_by_warehouse(
    db: AsyncSession,
    inventory_skus: list[str],
    *,
    warehouse_type: int | None = None,
    warehouse_types: Collection[int] | None = None,
    exclude_warehouse_type: int | None = None,
    exclude_warehouse_types: Collection[int] | None = None,
    sku_to_group_key: dict[str, str] | None = None,
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
    included_types = _type_filter_values(warehouse_type, warehouse_types)
    excluded_types = _type_filter_values(exclude_warehouse_type, exclude_warehouse_types)
    if included_types:
        stmt = stmt.where(Warehouse.type.in_(included_types))
    if excluded_types:
        stmt = stmt.where(~Warehouse.type.in_(excluded_types))
    rows = (await db.execute(stmt)).all()
    sku_groups = sku_to_group_key or {}
    result: dict[tuple[str, str], WarehouseStock] = {}
    for sku, warehouse_id, country, total in rows:
        key = (sku_groups.get(sku, sku), warehouse_id)
        current = result.get(key)
        if current is None:
            result[key] = WarehouseStock(country=country, total=int(total or 0))
        else:
            result[key] = WarehouseStock(
                country=current.country or country,
                total=current.total + int(total or 0),
            )
    return result


async def load_in_transit_totals_by_warehouse(
    db: AsyncSession,
    inventory_skus: list[str],
    *,
    warehouse_type: int | None = None,
    warehouse_types: Collection[int] | None = None,
    exclude_warehouse_type: int | None = None,
    exclude_warehouse_types: Collection[int] | None = None,
    sku_to_group_key: dict[str, str] | None = None,
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
    included_types = _type_filter_values(warehouse_type, warehouse_types)
    excluded_types = _type_filter_values(exclude_warehouse_type, exclude_warehouse_types)
    if included_types:
        stmt = stmt.where(Warehouse.type.in_(included_types))
    if excluded_types:
        stmt = stmt.where(~Warehouse.type.in_(excluded_types))
    rows = (await db.execute(stmt)).all()
    sku_groups = sku_to_group_key or {}
    result: dict[tuple[str, str], WarehouseStock] = {}
    for sku, warehouse_id, country, total in rows:
        key = (sku_groups.get(sku, sku), warehouse_id)
        current = result.get(key)
        if current is None:
            result[key] = WarehouseStock(country=country, total=int(total or 0))
        else:
            result[key] = WarehouseStock(
                country=current.country or country,
                total=current.total + int(total or 0),
            )
    return result


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
            merged[key] = WarehouseStock(
                country=current.country or stock.country, total=current.total + stock.total
            )
    return merged


def compute_mapped_stock_by_country(
    rules: MappingRules,
    component_stock: dict[tuple[str, str], WarehouseStock],
    *,
    velocity: dict[str, dict[str, float]] | None = None,
) -> dict[tuple[str, str], int]:
    """Return assembled commodity stock aggregated by ``(commodity_sku, country)``."""
    result: defaultdict[tuple[str, str], int] = defaultdict(int)
    if not rules or not component_stock:
        return {}

    allocations = _build_component_allocation(
        rules,
        component_stock,
        _country_weights_by_sku(velocity) if velocity is not None else {},
    )
    warehouse_ids = {warehouse_id for _, warehouse_id in component_stock}
    country_by_warehouse: dict[str, str] = {}
    component_keys = set(component_stock)
    for (_component_sku, warehouse_id), stock in component_stock.items():
        if stock.country and warehouse_id not in country_by_warehouse:
            country_by_warehouse[warehouse_id] = stock.country
    for commodity_sku, groups in rules.items():
        for warehouse_id in warehouse_ids:
            country = country_by_warehouse.get(warehouse_id)
            if not country or not is_reportable_country_code(country):
                continue
            for components in groups:
                has_component_signal = any(
                    (component.inventory_sku, warehouse_id) in component_keys
                    for component in components
                )
                if not has_component_signal:
                    continue
                buildable: int | None = None
                for component in components:
                    allocated_stock = allocations.get(
                        (commodity_sku, component.inventory_sku, warehouse_id)
                    )
                    if allocated_stock is None:
                        buildable = 0
                        break
                    buildable_for_component = allocated_stock.total // component.quantity
                    buildable = (
                        buildable_for_component
                        if buildable is None
                        else min(buildable, buildable_for_component)
                    )
                if buildable is not None:
                    result[(commodity_sku, country)] += buildable
    return dict(result)


async def load_in_transit_totals_by_country(
    db: AsyncSession,
    inventory_skus: list[str],
    *,
    sku_to_group_key: dict[str, str] | None = None,
) -> dict[tuple[str, str], int]:
    """Load component in-transit quantities that only have target countries."""
    if not inventory_skus:
        return {}
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
        .where(InTransitRecord.target_warehouse_id.is_(None))
        .where(InTransitRecord.target_country.is_not(None))
        .where(InTransitItem.commodity_sku.in_(inventory_skus))
        .group_by(InTransitItem.commodity_sku, InTransitRecord.target_country)
    )
    rows = (await db.execute(stmt)).all()
    sku_groups = sku_to_group_key or {}
    result: defaultdict[tuple[str, str], int] = defaultdict(int)
    for sku, country, total in rows:
        if not is_reportable_country_code(country):
            continue
        result[(sku_groups.get(sku, sku), country)] += int(total or 0)
    return dict(result)


def aggregate_component_stock_by_country(
    warehouse_stock: dict[tuple[str, str], WarehouseStock],
    country_stock: dict[tuple[str, str], int],
) -> dict[tuple[str, str], WarehouseStock]:
    """Collapse component stock into one synthetic warehouse per country."""
    result: dict[tuple[str, str], WarehouseStock] = {}
    for (sku, _warehouse_id), stock in warehouse_stock.items():
        if not stock.country or not is_reportable_country_code(stock.country):
            continue
        key = (sku, _country_level_warehouse_id(stock.country))
        current = result.get(key)
        if current is None:
            result[key] = WarehouseStock(country=stock.country, total=stock.total)
        else:
            result[key] = WarehouseStock(country=stock.country, total=current.total + stock.total)
    for (sku, country), total in country_stock.items():
        if not is_reportable_country_code(country):
            continue
        key = (sku, _country_level_warehouse_id(country))
        current = result.get(key)
        if current is None:
            result[key] = WarehouseStock(country=country, total=int(total or 0))
        else:
            result[key] = WarehouseStock(country=country, total=current.total + int(total or 0))
    return result


def _country_level_warehouse_id(country: str) -> str:
    return f"__country_pool__:{country}"


def compute_mapped_stock_total_by_sku(
    rules: MappingRules,
    component_stock: dict[tuple[str, str], WarehouseStock],
    *,
    velocity: dict[str, dict[str, float]] | None = None,
) -> dict[str, int]:
    """Return assembled local stock aggregated by commodity SKU."""
    totals: defaultdict[str, int] = defaultdict(int)
    if not rules or not component_stock:
        return {}

    allocations = _build_component_allocation(
        rules,
        component_stock,
        _local_weights_by_sku(velocity) if velocity is not None else {},
        fixed_weight_country="",
    )
    warehouse_ids = {warehouse_id for _, warehouse_id in component_stock}
    for commodity_sku, groups in rules.items():
        for warehouse_id in warehouse_ids:
            for components in groups:
                buildable: int | None = None
                for component in components:
                    stock = allocations.get((commodity_sku, component.inventory_sku, warehouse_id))
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
