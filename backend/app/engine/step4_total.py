"""Step 4: calculate procurement quantity."""

from __future__ import annotations

import math

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.engine.context import EngineContext, LocalStock
from app.engine.sku_mapping import (
    component_skus_for_rules,
    compute_mapped_stock_total_by_sku,
    load_active_mapping_rules,
    load_inventory_totals_by_warehouse,
)
from app.models.inventory import InventorySnapshotLatest
from app.models.warehouse import Warehouse

logger = get_logger(__name__)


async def load_local_inventory(
    db: AsyncSession,
    commodity_skus: list[str] | None,
) -> dict[str, LocalStock]:
    stmt = (
        select(
            InventorySnapshotLatest.commodity_sku,
            func.sum(InventorySnapshotLatest.available).label("avail"),
            func.sum(InventorySnapshotLatest.reserved).label("reserv"),
        )
        .join(Warehouse, Warehouse.id == InventorySnapshotLatest.warehouse_id)
        .where(Warehouse.type == 1)
        .group_by(InventorySnapshotLatest.commodity_sku)
    )
    if commodity_skus is not None:
        stmt = stmt.where(InventorySnapshotLatest.commodity_sku.in_(commodity_skus))
    rows = (await db.execute(stmt)).all()
    result = {sku: LocalStock(available=int(a or 0), reserved=int(r or 0)) for sku, a, r in rows}

    rules = await load_active_mapping_rules(db, commodity_skus)
    component_skus = component_skus_for_rules(rules)
    if component_skus:
        component_inventory = await load_inventory_totals_by_warehouse(
            db,
            component_skus,
            warehouse_type=1,
        )
        mapped_totals = compute_mapped_stock_total_by_sku(rules, component_inventory)
        for sku, quantity in mapped_totals.items():
            current = result.get(sku)
            if current is None:
                result[sku] = LocalStock(available=quantity, reserved=0)
            else:
                result[sku] = LocalStock(available=current.available + quantity, reserved=current.reserved)
    return result


def compute_total(
    sku: str,
    country_qty_for_sku: dict[str, int],
    velocity_for_sku: dict[str, float],
    local_stock_for_sku: LocalStock | None,
    buffer_days: int,
    safety_stock_days: int = 0,
) -> int:
    sum_qty = sum(country_qty_for_sku.values())
    sum_velocity = sum(velocity_for_sku.values())
    safety_qty = math.ceil(sum_velocity * safety_stock_days)
    local_total = local_stock_for_sku.total if local_stock_for_sku is not None else 0
    raw_purchase_qty = sum_qty - local_total + safety_qty
    # 本地库存过剩时公式可能为负，夹到 0（DB 侧也有 CheckConstraint 双保险）
    purchase_qty = max(0, int(raw_purchase_qty))
    logger.info(
        "step4_purchase_qty_computed",
        sku=sku,
        sum_qty=sum_qty,
        sum_velocity=sum_velocity,
        safety_qty=safety_qty,
        local_total=local_total,
        raw_purchase_qty=raw_purchase_qty,
        purchase_qty=purchase_qty,
    )
    return purchase_qty


def step4_total(ctx: EngineContext) -> dict[str, int]:
    """Return ``{sku: purchase_qty}`` for all SKUs with engine signals."""
    result: dict[str, int] = {}
    all_skus = set(ctx.country_qty) | set(ctx.velocity) | set(ctx.local_stock)
    for sku in all_skus:
        result[sku] = compute_total(
            sku=sku,
            country_qty_for_sku=ctx.country_qty.get(sku, {}),
            velocity_for_sku=ctx.velocity.get(sku, {}),
            local_stock_for_sku=ctx.local_stock.get(sku),
            buffer_days=ctx.buffer_days,
            safety_stock_days=ctx.safety_stock_days,
        )
    return result
