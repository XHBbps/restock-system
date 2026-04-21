"""Suggestion REST API."""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import case, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.api.deps import UserContext, db_session, get_current_user, require_permission
from app.core.exceptions import ConflictError, NotFound, ValidationFailed
from app.core.permissions import HISTORY_DELETE, RESTOCK_OPERATE, RESTOCK_VIEW
from app.core.query import escape_like
from app.core.timezone import BEIJING, now_beijing
from app.engine.step6_timing import has_urgent_sale_days, positive_qty_countries
from app.models.product_listing import ProductListing
from app.models.sku import SkuConfig
from app.models.suggestion import Suggestion, SuggestionItem
from app.models.suggestion_snapshot import SuggestionSnapshot
from app.schemas.suggestion import (
    SuggestionDetailOut,
    SuggestionItemOut,
    SuggestionItemPatch,
    SuggestionListOut,
    SuggestionOut,
)

router = APIRouter(prefix="/api/suggestions", tags=["suggestion"])

SUGGESTION_STATUS_SORT_ORDER: dict[str, int] = {"draft": 0, "archived": 1, "error": 2}


def _suggestion_status_sort_expr() -> ColumnElement[int]:
    return case(
        *[(Suggestion.status == status, order) for status, order in SUGGESTION_STATUS_SORT_ORDER.items()],
        else_=len(SUGGESTION_STATUS_SORT_ORDER),
    )


def _apply_suggestion_sort(stmt, sort_by: str | None, sort_order: str):
    sort_map: dict[str, tuple[ColumnElement[object], ...]] = {
        "id": (Suggestion.id,),
        "created_at": (Suggestion.created_at,),
        "triggered_by": (Suggestion.triggered_by,),
        "status": (_suggestion_status_sort_expr(),),
        "total_items": (Suggestion.total_items,),
    }
    columns = sort_map.get(sort_by or "", (Suggestion.created_at,))
    ordered_columns = [column.asc() if sort_order == "asc" else column.desc() for column in columns]
    return stmt.order_by(*ordered_columns, Suggestion.created_at.desc(), Suggestion.id.desc())


def _procurement_snapshot_count_sq():
    return (
        select(func.count(SuggestionSnapshot.id))
        .where(SuggestionSnapshot.suggestion_id == Suggestion.id)
        .where(SuggestionSnapshot.snapshot_type == "procurement")
        .correlate(Suggestion)
        .scalar_subquery()
    )


def _restock_snapshot_count_sq():
    return (
        select(func.count(SuggestionSnapshot.id))
        .where(SuggestionSnapshot.suggestion_id == Suggestion.id)
        .where(SuggestionSnapshot.snapshot_type == "restock")
        .correlate(Suggestion)
        .scalar_subquery()
    )


@router.get("", response_model=SuggestionListOut)
async def list_suggestions(
    status: str | None = Query(default=None),
    display_status: Literal["pending", "exported", "archived", "error"] | None = Query(default=None),
    date_from: date_type | None = Query(default=None),
    date_to: date_type | None = Query(default=None),
    sku: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=5000),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(db_session),
    _: None = Depends(require_permission(RESTOCK_VIEW)),
) -> SuggestionListOut:
    procurement_snapshot_count_sq = _procurement_snapshot_count_sq()
    restock_snapshot_count_sq = _restock_snapshot_count_sq()
    total_snapshot_count_sq = procurement_snapshot_count_sq + restock_snapshot_count_sq

    base = select(Suggestion)
    if display_status == "pending":
        base = base.where(Suggestion.status == "draft", total_snapshot_count_sq == 0)
    elif display_status == "exported":
        base = base.where(Suggestion.status == "draft", total_snapshot_count_sq > 0)
    elif display_status == "archived":
        base = base.where(Suggestion.status == "archived")
    elif display_status == "error":
        base = base.where(Suggestion.status == "error")
    elif status:
        base = base.where(Suggestion.status == status)

    if date_from:
        base = base.where(
            Suggestion.created_at >= datetime.combine(date_from, datetime.min.time(), tzinfo=BEIJING)
        )
    if date_to:
        base = base.where(
            Suggestion.created_at
            < datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tzinfo=BEIJING)
        )
    if sku:
        subq = (
            select(SuggestionItem.suggestion_id)
            .where(SuggestionItem.commodity_sku.ilike(f"%{escape_like(sku)}%", escape="\\"))
            .subquery()
        )
        base = base.where(Suggestion.id.in_(select(subq.c.suggestion_id)))

    base = _apply_suggestion_sort(base, sort_by, sort_order)
    total = (await db.execute(base.with_only_columns(func.count()).order_by(None))).scalar_one()
    rows = (
        await db.execute(
            base.add_columns(
                procurement_snapshot_count_sq.label("procurement_snapshot_count"),
                restock_snapshot_count_sq.label("restock_snapshot_count"),
            ).offset((page - 1) * page_size).limit(page_size)
        )
    ).all()

    items: list[SuggestionOut] = []
    for suggestion, procurement_snapshot_count, restock_snapshot_count in rows:
        items.append(
            SuggestionOut.model_validate(
                {
                    **suggestion.__dict__,
                    "procurement_snapshot_count": int(procurement_snapshot_count or 0),
                    "restock_snapshot_count": int(restock_snapshot_count or 0),
                }
            )
        )

    return SuggestionListOut(items=items, total=int(total or 0), page=page, page_size=page_size)


@router.get("/current", response_model=SuggestionDetailOut)
async def get_current_suggestion(
    db: AsyncSession = Depends(db_session),
    _: None = Depends(require_permission(RESTOCK_VIEW)),
) -> SuggestionDetailOut:
    suggestion = (
        await db.execute(
            select(Suggestion).where(Suggestion.status == "draft").order_by(Suggestion.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if suggestion is None:
        raise NotFound("当前没有活动的建议单")
    return await _build_detail(db, suggestion)


@router.get("/{suggestion_id}", response_model=SuggestionDetailOut)
async def get_suggestion(
    suggestion_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: None = Depends(require_permission(RESTOCK_VIEW)),
) -> SuggestionDetailOut:
    suggestion = (
        await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    ).scalar_one_or_none()
    if suggestion is None:
        raise NotFound(f"建议单 {suggestion_id} 不存在")
    return await _build_detail(db, suggestion)


@router.patch("/{suggestion_id}/items/{item_id}", response_model=SuggestionItemOut)
async def patch_item(
    patch: SuggestionItemPatch,
    suggestion_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: None = Depends(require_permission(RESTOCK_OPERATE)),
) -> SuggestionItemOut:
    parent = (
        await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    ).scalar_one_or_none()
    if parent is None:
        raise NotFound(f"建议单 {suggestion_id} 不存在")
    if parent.status == "archived":
        raise ValidationFailed("已归档的建议单不可编辑")

    item = (
        await db.execute(
            select(SuggestionItem).where(
                SuggestionItem.id == item_id,
                SuggestionItem.suggestion_id == suggestion_id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise NotFound(f"建议条目 {item_id} 不存在")
    if item.procurement_export_status == "exported" or item.restock_export_status == "exported":
        raise ValidationFailed("已导出的条目不可编辑")

    effective_country_breakdown = (
        patch.country_breakdown if patch.country_breakdown is not None else (item.country_breakdown or {})
    )
    effective_warehouse_breakdown = (
        patch.warehouse_breakdown
        if patch.warehouse_breakdown is not None
        else (item.warehouse_breakdown or {})
    )
    for country in positive_qty_countries(effective_country_breakdown):
        warehouse_values = list((effective_warehouse_breakdown.get(country) or {}).values())
        if warehouse_values and sum(warehouse_values) != effective_country_breakdown[country]:
            raise ValidationFailed(f"{country} 的 warehouse_breakdown 之和与 country_breakdown 不一致")

    updates: dict[str, Any] = {}
    if patch.total_qty is not None:
        updates["total_qty"] = patch.total_qty
    if patch.purchase_qty is not None:
        updates["purchase_qty"] = patch.purchase_qty
    if "purchase_date" in patch.model_fields_set:
        updates["purchase_date"] = patch.purchase_date
    if patch.country_breakdown is not None:
        updates["country_breakdown"] = patch.country_breakdown
        updates["total_qty"] = sum(patch.country_breakdown.values())
    if patch.warehouse_breakdown is not None:
        updates["warehouse_breakdown"] = patch.warehouse_breakdown
    if patch.country_breakdown is not None or patch.warehouse_breakdown is not None:
        updates["allocation_snapshot"] = None
    if patch.country_breakdown is not None:
        lead_time_days = await _resolve_effective_lead_time_days(db, parent, item)
        updates["urgent"] = has_urgent_sale_days(
            item.sale_days_snapshot or {},
            lead_time_days=lead_time_days,
            countries=positive_qty_countries(effective_country_breakdown),
        )

    if updates:
        await db.execute(update(SuggestionItem).where(SuggestionItem.id == item_id).values(**updates))
        await db.refresh(item)

    return await _enrich_item(db, item)


@router.post("/{suggestion_id}/archive", status_code=204)
async def archive_suggestion(
    suggestion_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: None = Depends(require_permission(RESTOCK_OPERATE)),
) -> None:
    suggestion = (
        await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    ).scalar_one_or_none()
    if suggestion is None:
        raise NotFound(f"建议单 {suggestion_id} 不存在")
    if suggestion.status == "archived":
        raise ConflictError("建议单已归档")
    await db.execute(
        update(Suggestion).where(Suggestion.id == suggestion_id).values(status="archived", archived_at=now_beijing())
    )


@router.delete("/{suggestion_id}", status_code=204)
async def delete_suggestion(
    suggestion_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: None = Depends(require_permission(HISTORY_DELETE)),
) -> None:
    suggestion = (
        await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    ).scalar_one_or_none()
    if suggestion is None:
        raise NotFound(f"建议单 {suggestion_id} 不存在")

    snapshot_count = (
        await db.execute(select(func.count()).select_from(SuggestionSnapshot).where(SuggestionSnapshot.suggestion_id == suggestion_id))
    ).scalar_one()
    if int(snapshot_count or 0) > 0:
        raise ConflictError(f"建议单已存在 {snapshot_count} 个快照，不可删除")

    await db.execute(delete(Suggestion).where(Suggestion.id == suggestion_id))


@router.post("/{suggestion_id}/void", status_code=204)
async def void_suggestion(
    suggestion_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(HISTORY_DELETE)),
) -> None:
    """作废建议单：status=draft → archived + archived_trigger='voided'。

    作废后建议单从"发起页"消失，保留在"历史记录"里显示为"已作废"状态。
    和删除不同：作废保留记录（包括已导出的 snapshot）；删除彻底抹除。
    """
    suggestion = (
        await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    ).scalar_one_or_none()
    if suggestion is None:
        raise NotFound(f"建议单 {suggestion_id} 不存在")
    if suggestion.status != "draft":
        raise ConflictError(f"只有 draft 状态的建议单可作废，当前状态={suggestion.status}")

    await db.execute(
        update(Suggestion)
        .where(Suggestion.id == suggestion_id)
        .values(
            status="archived",
            archived_trigger="voided",
            archived_by=user.id,
            archived_at=now_beijing(),
        )
    )


async def _resolve_effective_lead_time_days(
    db: AsyncSession,
    suggestion: Suggestion,
    item: SuggestionItem,
) -> int:
    row = (
        await db.execute(select(SkuConfig.lead_time_days).where(SkuConfig.commodity_sku == item.commodity_sku))
    ).first()
    sku_lead_time = row[0] if row else None
    if sku_lead_time is not None:
        return int(sku_lead_time)
    snapshot_lead_time = (suggestion.global_config_snapshot or {}).get("lead_time_days")
    if isinstance(snapshot_lead_time, (int, float)):
        return int(snapshot_lead_time)
    return 50


async def _snapshot_counts_for_suggestion(
    db: AsyncSession,
    suggestion_id: int,
) -> tuple[int, int]:
    rows = (
        await db.execute(
            select(
                func.sum(case((SuggestionSnapshot.snapshot_type == "procurement", 1), else_=0)),
                func.sum(case((SuggestionSnapshot.snapshot_type == "restock", 1), else_=0)),
            ).where(SuggestionSnapshot.suggestion_id == suggestion_id)
        )
    ).one()
    return int(rows[0] or 0), int(rows[1] or 0)


async def _build_detail(db: AsyncSession, suggestion: Suggestion) -> SuggestionDetailOut:
    items = (
        await db.execute(
            select(SuggestionItem)
            .where(SuggestionItem.suggestion_id == suggestion.id)
            .order_by(SuggestionItem.urgent.desc(), SuggestionItem.id)
        )
    ).scalars().all()

    sku_codes = [item.commodity_sku for item in items]
    name_map: dict[str, tuple[str | None, str | None]] = {}
    if sku_codes:
        rows = (
            await db.execute(
                select(
                    ProductListing.commodity_sku,
                    ProductListing.commodity_name,
                    ProductListing.main_image,
                ).where(ProductListing.commodity_sku.in_(sku_codes))
            )
        ).all()
        for sku, name, image in rows:
            if sku not in name_map:
                name_map[sku] = (name, image)

    enriched_items = [
        SuggestionItemOut.model_validate(
            {
                **item.__dict__,
                "commodity_name": name_map.get(item.commodity_sku, (None, None))[0],
                "main_image": name_map.get(item.commodity_sku, (None, None))[1],
            }
        )
        for item in items
    ]
    procurement_snapshot_count, restock_snapshot_count = await _snapshot_counts_for_suggestion(
        db, suggestion.id
    )
    return SuggestionDetailOut(
        **SuggestionOut.model_validate(
            {
                **suggestion.__dict__,
                "procurement_snapshot_count": procurement_snapshot_count,
                "restock_snapshot_count": restock_snapshot_count,
            }
        ).model_dump(),
        items=enriched_items,
    )


async def _enrich_item(db: AsyncSession, item: SuggestionItem) -> SuggestionItemOut:
    row = (
        await db.execute(
            select(ProductListing.commodity_name, ProductListing.main_image)
            .where(ProductListing.commodity_sku == item.commodity_sku)
            .limit(1)
        )
    ).first()
    commodity_name = row[0] if row else None
    main_image = row[1] if row else None
    return SuggestionItemOut.model_validate(
        {**item.__dict__, "commodity_name": commodity_name, "main_image": main_image}
    )
