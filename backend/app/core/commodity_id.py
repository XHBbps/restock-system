"""Helpers for resolving and refreshing suggestion commodity IDs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app.models.product_listing import ProductListing
from app.models.suggestion import SuggestionItem

MISSING_COMMODITY_ID_BLOCKER = "missing_commodity_id"

_LOOKUP_STRATEGIES: tuple[tuple[InstrumentedAttribute[Any], bool | None, bool | None], ...] = (
    (ProductListing.commodity_sku, True, True),
    (ProductListing.commodity_sku, True, None),
    (ProductListing.commodity_sku, None, None),
    (ProductListing.seller_sku, True, True),
    (ProductListing.seller_sku, True, None),
    (ProductListing.seller_sku, None, None),
)


async def resolve_commodity_id_map(
    db: AsyncSession,
    skus: Iterable[str],
) -> dict[str, str | None]:
    """Resolve SKU -> commodity_id with progressively wider fallback queries."""
    normalized_skus = sorted({sku for sku in skus if sku})
    resolved: dict[str, str | None] = {sku: None for sku in normalized_skus}
    unresolved = set(normalized_skus)
    if not unresolved:
        return resolved

    for key_field, require_matched, require_active in _LOOKUP_STRATEGIES:
        rows = await _query_commodity_ids(
            db,
            key_field=key_field,
            skus=unresolved,
            require_matched=require_matched,
            require_active=require_active,
        )
        for sku, commodity_id in rows:
            if sku in unresolved and commodity_id:
                resolved[sku] = commodity_id
                unresolved.remove(sku)
        if not unresolved:
            break

    return resolved


async def refresh_suggestion_item_pushability(
    db: AsyncSession,
    items: Iterable[SuggestionItem],
) -> set[int]:
    """Backfill missing commodity IDs and normalize blocker/push status in-place."""
    candidates = [
        item
        for item in items
        if item.push_status != "pushed"
        and (item.push_blocker == MISSING_COMMODITY_ID_BLOCKER or not item.commodity_id)
    ]
    if not candidates:
        return set()

    resolved_ids = await resolve_commodity_id_map(
        db,
        [item.commodity_sku for item in candidates],
    )

    updated_item_ids: set[int] = set()
    for item in candidates:
        resolved_id = resolved_ids.get(item.commodity_sku)
        values: dict[str, Any] = {}

        if resolved_id:
            if item.commodity_id != resolved_id:
                values["commodity_id"] = resolved_id
            if item.push_blocker == MISSING_COMMODITY_ID_BLOCKER:
                values["push_blocker"] = None
            if item.push_status == "blocked":
                values["push_status"] = "pending"
        elif not item.commodity_id:
            if item.push_blocker != MISSING_COMMODITY_ID_BLOCKER:
                values["push_blocker"] = MISSING_COMMODITY_ID_BLOCKER
            if item.push_status == "pending":
                values["push_status"] = "blocked"

        if not values:
            continue

        await db.execute(
            update(SuggestionItem).where(SuggestionItem.id == item.id).values(**values)
        )
        for key, value in values.items():
            setattr(item, key, value)
        updated_item_ids.add(item.id)

    return updated_item_ids


async def _query_commodity_ids(
    db: AsyncSession,
    *,
    key_field: InstrumentedAttribute[Any],
    skus: set[str],
    require_matched: bool | None,
    require_active: bool | None,
) -> list[tuple[str, str]]:
    if not skus:
        return []

    stmt = (
        select(key_field, ProductListing.commodity_id)
        .where(key_field.in_(sorted(skus)))
        .where(ProductListing.commodity_id.is_not(None))
        .order_by(
            key_field,
            ProductListing.updated_at.desc(),
            ProductListing.last_sync_at.desc(),
            ProductListing.commodity_id,
        )
    )
    if require_matched is not None:
        stmt = stmt.where(ProductListing.is_matched.is_(require_matched))
    if require_active is True:
        stmt = stmt.where(ProductListing.online_status == "active")

    return [(str(sku), str(commodity_id)) for sku, commodity_id in (await db.execute(stmt)).all()]
