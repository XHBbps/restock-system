"""Suggestion REST API."""

from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import Float, case, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.api.deps import db_session, get_current_session
from app.core.commodity_id import refresh_suggestion_item_pushability
from app.core.exceptions import ConflictError, NotFound, PushBlockedError, ValidationFailed
from app.core.query import escape_like
from app.core.timezone import BEIJING, now_beijing
from app.engine.step6_timing import has_urgent_purchase, positive_qty_countries
from app.models.product_listing import ProductListing
from app.models.suggestion import Suggestion, SuggestionItem
from app.schemas.suggestion import (
    PushRequest,
    SuggestionDetailOut,
    SuggestionItemOut,
    SuggestionItemPatch,
    SuggestionListOut,
    SuggestionOut,
)
from app.tasks.queue import enqueue_task

router = APIRouter(prefix="/api/suggestions", tags=["suggestion"])

SUGGESTION_STATUS_SORT_ORDER: dict[str, int] = {
    "draft": 0,
    "partial": 1,
    "pushed": 2,
    "archived": 3,
    "error": 4,
}


def _suggestion_status_sort_expr() -> ColumnElement[int]:
    return case(
        *[
            (Suggestion.status == status, order)
            for status, order in SUGGESTION_STATUS_SORT_ORDER.items()
        ],
        else_=len(SUGGESTION_STATUS_SORT_ORDER),
    )


def _success_rate_sort_expr() -> ColumnElement[float]:
    return func.coalesce(
        Suggestion.pushed_items.cast(Float) / func.nullif(Suggestion.total_items, 0),
        -1.0,
    )


def _apply_suggestion_sort(stmt, sort_by: str | None, sort_order: str):
    success_rate_expr = _success_rate_sort_expr()
    sort_map: dict[str, tuple[ColumnElement[object], ...]] = {
        "id": (Suggestion.id,),
        "created_at": (Suggestion.created_at,),
        "triggered_by": (Suggestion.triggered_by,),
        "status": (_suggestion_status_sort_expr(),),
        "total_items": (Suggestion.total_items,),
        "pushed_items": (Suggestion.pushed_items,),
        "failed_items": (Suggestion.failed_items,),
        "success_rate": (
            case((Suggestion.total_items == 0, 1), else_=0),
            success_rate_expr,
        ),
    }
    columns = sort_map.get(sort_by or "", (Suggestion.created_at,))
    ordered_columns = [
        column.asc() if sort_order == "asc" else column.desc() for column in columns
    ]
    return stmt.order_by(*ordered_columns, Suggestion.created_at.desc(), Suggestion.id.desc())


@router.get("", response_model=SuggestionListOut)
async def list_suggestions(
    status: str | None = Query(default=None),
    date_from: date_type | None = Query(default=None),
    date_to: date_type | None = Query(default=None),
    sku: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=5000),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> SuggestionListOut:
    base = select(Suggestion)
    if status:
        base = base.where(Suggestion.status == status)
    if date_from:
        base = base.where(
            Suggestion.created_at
            >= datetime.combine(date_from, datetime.min.time(), tzinfo=BEIJING)
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
    count_stmt = base.with_only_columns(func.count()).order_by(None)
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(base.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return SuggestionListOut(
        items=[SuggestionOut.model_validate(row) for row in rows],
        total=int(total or 0),
    )


@router.get("/current", response_model=SuggestionDetailOut)
async def get_current_suggestion(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> SuggestionDetailOut:
    row = (
        await db.execute(
            select(Suggestion)
            .where(Suggestion.status.in_(("draft", "partial")))
            .order_by(Suggestion.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("当前没有活动的建议单")
    return await _build_detail(db, row)


@router.get("/{suggestion_id}", response_model=SuggestionDetailOut)
async def get_suggestion(
    suggestion_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> SuggestionDetailOut:
    row = (
        await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(f"建议单 {suggestion_id} 不存在")
    return await _build_detail(db, row)


@router.patch("/{suggestion_id}/items/{item_id}", response_model=SuggestionItemOut)
async def patch_item(
    patch: SuggestionItemPatch,
    suggestion_id: int = Path(..., ge=1),
    item_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
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
    if item.push_status == "pushed":
        raise ValidationFailed("已推送的明细不可编辑")

    if patch.country_breakdown is not None:
        for value in patch.country_breakdown.values():
            if value < 0:
                raise ValidationFailed("country_breakdown 包含负数")
    if patch.warehouse_breakdown is not None:
        for inner in patch.warehouse_breakdown.values():
            for value in inner.values():
                if value < 0:
                    raise ValidationFailed("warehouse_breakdown 包含负数")

    effective_country_breakdown = (
        patch.country_breakdown
        if patch.country_breakdown is not None
        else (item.country_breakdown or {})
    )
    effective_warehouse_breakdown = (
        patch.warehouse_breakdown
        if patch.warehouse_breakdown is not None
        else (item.warehouse_breakdown or {})
    )
    effective_t_purchase = dict(item.t_purchase or {})
    if patch.t_purchase is not None:
        effective_t_purchase.update(patch.t_purchase)

    today = now_beijing().date()
    today_iso = today.isoformat()
    for country in positive_qty_countries(effective_country_breakdown):
        effective_t_purchase.setdefault(country, today_iso)

    from datetime import date as _date

    for country, value in effective_t_purchase.items():
        if isinstance(value, str):
            try:
                _date.fromisoformat(value)
            except (ValueError, TypeError) as exc:
                raise ValidationFailed(f"t_purchase[{country}] 包含无效日期: {exc}") from exc

    for country in positive_qty_countries(effective_country_breakdown):
        warehouse_values = list((effective_warehouse_breakdown.get(country) or {}).values())
        if warehouse_values and sum(warehouse_values) != effective_country_breakdown[country]:
            raise ValidationFailed(
                f"{country} 的 warehouse_breakdown 之和与 country_breakdown 不一致"
            )

    updates: dict[str, Any] = {}
    if patch.total_qty is not None:
        updates["total_qty"] = patch.total_qty
    if patch.country_breakdown is not None:
        updates["country_breakdown"] = patch.country_breakdown
    if patch.warehouse_breakdown is not None:
        updates["warehouse_breakdown"] = patch.warehouse_breakdown
    if patch.country_breakdown is not None or patch.warehouse_breakdown is not None:
        updates["allocation_snapshot"] = None
    if patch.t_purchase is not None or any(
        country not in (item.t_purchase or {})
        for country in positive_qty_countries(effective_country_breakdown)
    ):
        updates["t_purchase"] = effective_t_purchase

    if (
        patch.t_purchase is not None
        or patch.total_qty is not None
        or patch.country_breakdown is not None
    ):
        updates["urgent"] = has_urgent_purchase(
            effective_t_purchase,
            today=today,
            countries=positive_qty_countries(effective_country_breakdown),
        )

    if updates:
        await db.execute(
            update(SuggestionItem).where(SuggestionItem.id == item_id).values(**updates)
        )
        await db.refresh(item)

    return await _enrich_item(db, item)


@router.post("/{suggestion_id}/push")
async def push_items(
    req: PushRequest,
    suggestion_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> dict[str, Any]:
    sug = (
        await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    ).scalar_one_or_none()
    if sug is None:
        raise NotFound(f"建议单 {suggestion_id} 不存在")
    if sug.status not in ("draft", "partial"):
        raise ConflictError(f"建议单状态为 {sug.status}, 不可推送")

    items = (
        await db.execute(
            select(SuggestionItem).where(
                SuggestionItem.id.in_(req.item_ids),
                SuggestionItem.suggestion_id == suggestion_id,
            )
        )
    ).scalars().all()
    if len(items) != len(req.item_ids):
        raise NotFound("部分条目不存在")

    await refresh_suggestion_item_pushability(db, items)

    blocked = [it.id for it in items if it.push_blocker]
    if blocked:
        raise PushBlockedError(
            f"以下条目带有 push_blocker,无法推送: {blocked}",
            detail={"blocked_item_ids": blocked},
        )
    zero_qty = [it.id for it in items if (it.total_qty or 0) <= 0]
    if zero_qty:
        raise PushBlockedError(
            f"以下条目 total_qty<=0,无法推送: {zero_qty}",
            detail={"zero_qty_item_ids": zero_qty},
        )
    already_pushed = [it.id for it in items if it.push_status == "pushed"]
    if already_pushed:
        raise ConflictError(
            f"以下条目已推送,不可重复推送: {already_pushed}",
            detail={"already_pushed_item_ids": already_pushed},
        )

    task_id, existing = await enqueue_task(
        db,
        job_name="push_saihu",
        trigger_source="manual",
        dedupe_key=f"push_saihu#{suggestion_id}",
        payload={"suggestion_id": suggestion_id, "item_ids": req.item_ids},
    )
    return {"task_id": task_id, "existing": existing}


@router.post("/{suggestion_id}/archive", status_code=204)
async def archive_suggestion(
    suggestion_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> None:
    sug = (
        await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    ).scalar_one_or_none()
    if sug is None:
        raise NotFound(f"建议单 {suggestion_id} 不存在")
    if sug.status == "archived":
        raise ConflictError("建议单已归档")
    await db.execute(
        update(Suggestion)
        .where(Suggestion.id == suggestion_id)
        .values(status="archived", archived_at=now_beijing())
    )
    return None


@router.delete("/{suggestion_id}", status_code=204)
async def delete_suggestion(
    suggestion_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> None:
    sug = (
        await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    ).scalar_one_or_none()
    if sug is None:
        raise NotFound(f"建议单 {suggestion_id} 不存在")
    if sug.status == "pushed":
        raise ConflictError("已推送的建议单不可删除")

    await db.execute(delete(Suggestion).where(Suggestion.id == suggestion_id))
    return None


async def _build_detail(db: AsyncSession, sug: Suggestion) -> SuggestionDetailOut:
    items = (
        await db.execute(
            select(SuggestionItem)
            .where(SuggestionItem.suggestion_id == sug.id)
            .order_by(SuggestionItem.urgent.desc(), SuggestionItem.id)
        )
    ).scalars().all()
    await refresh_suggestion_item_pushability(db, items)

    sku_codes = [it.commodity_sku for it in items]
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

    enriched = [
        SuggestionItemOut.model_validate(
            {
                **it.__dict__,
                "commodity_name": name_map.get(it.commodity_sku, (None, None))[0],
                "main_image": name_map.get(it.commodity_sku, (None, None))[1],
            }
        )
        for it in items
    ]
    return SuggestionDetailOut(
        **SuggestionOut.model_validate(sug).model_dump(),
        items=enriched,
    )


async def _enrich_item(db: AsyncSession, item: SuggestionItem) -> SuggestionItemOut:
    row = (
        await db.execute(
            select(ProductListing.commodity_name, ProductListing.main_image)
            .where(ProductListing.commodity_sku == item.commodity_sku)
            .limit(1)
        )
    ).first()
    name = row[0] if row else None
    image = row[1] if row else None
    return SuggestionItemOut.model_validate(
        {**item.__dict__, "commodity_name": name, "main_image": image}
    )
