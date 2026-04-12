"""Step 2: sale_days from overseas stock.

Formula (FR-030):
    sale_days[country] = (available + reserved + in_transit) / velocity[country]

Current business rule:
- available + reserved still come from overseas warehouse inventory
- in_transit comes from pushed (unarchived) suggestion items' country_breakdown
"""

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
    """Load in-transit quantities from recently pushed (unarchived) suggestion items.

    Already-pushed suggestion items represent planned replenishment that hasn't
    arrived yet. Their country_breakdown quantities are treated as in-transit
    stock to prevent the engine from generating duplicate suggestions.

    Only considers suggestions created within the last 90 days to avoid
    accumulating unbounded historical data.
    """
    from datetime import timedelta

    from app.core.timezone import now_beijing
    from app.models.suggestion import Suggestion, SuggestionItem

    # 海运通常 30-45 天,90 天覆盖绝大多数正常物流周期。
    # 超过 90 天未到货通常意味着物流异常(丢件),不算在途反而正确。
    cutoff = now_beijing() - timedelta(days=90)

    stmt = (
        select(
            SuggestionItem.commodity_sku,
            SuggestionItem.country_breakdown,
        )
        .join(Suggestion, Suggestion.id == SuggestionItem.suggestion_id)
        .where(SuggestionItem.push_status == "pushed")
        .where(Suggestion.status != "archived")
        .where(Suggestion.created_at >= cutoff)
    )
    if commodity_skus is not None:
        stmt = stmt.where(SuggestionItem.commodity_sku.in_(commodity_skus))

    rows = (await db.execute(stmt)).all()

    result: dict[tuple[str, str], int] = {}
    for sku, breakdown in rows:
        if not breakdown:
            continue
        for country, qty in breakdown.items():
            key = (sku, country)
            result[key] = result.get(key, 0) + int(qty)
    return result


def merge_inventory(
    oversea: dict[tuple[str, str], dict[str, int]],
    in_transit: dict[tuple[str, str], int],
) -> dict[str, dict[str, dict[str, int]]]:
    """Merge overseas stock and in-transit stock into one structure.

    Returns: ``{sku: {country: {available, reserved, in_transit, total}}}``
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
    """Compute ``sale_days`` for each ``(sku, country)`` with positive velocity."""
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
