"""建议单 REST API(对应 contracts/suggestion.yaml)。"""

from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import Float, case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.api.deps import db_session, get_current_session
from app.core.exceptions import ConflictError, NotFound, PushBlockedError, ValidationFailed
from app.core.query import escape_like
from app.core.timezone import BEIJING, now_beijing
from app.engine.step6_timing import (
    has_urgent_purchase,
    missing_timing_countries,
    positive_qty_countries,
)
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
    ordered_columns = [column.asc() if sort_order == "asc" else column.desc() for column in columns]
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
        # 用 EXISTS 子查询匹配 sku
        subq = (
            select(SuggestionItem.suggestion_id)
            .where(SuggestionItem.commodity_sku.ilike(f"%{escape_like(sku)}%", escape="\\"))
            .subquery()
        )
        base = base.where(Suggestion.id.in_(select(subq.c.suggestion_id)))

    base = _apply_suggestion_sort(base, sort_by, sort_order)
    count_stmt = base.with_only_columns(func.count()).order_by(None)
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (await db.execute(base.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return SuggestionListOut(
        items=[SuggestionOut.model_validate(r) for r in rows],
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
        raise NotFound("当前没有活跃的建议单")
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
    # N1: load parent suggestion first to enforce editable state
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

    # 非负校验
    if patch.country_breakdown is not None:
        for v in patch.country_breakdown.values():
            if v < 0:
                raise ValidationFailed("country_breakdown 包含负数")
    if patch.warehouse_breakdown is not None:
        for inner in patch.warehouse_breakdown.values():
            for v in inner.values():
                if v < 0:
                    raise ValidationFailed("warehouse_breakdown 包含负数")

    # H4:total_qty 与 country_breakdown 一致性(仅当两者同时提交时校验)
    if (
        patch.total_qty is not None
        and patch.country_breakdown is not None
        and sum(patch.country_breakdown.values()) != patch.total_qty
    ):
        raise ValidationFailed("country_breakdown 之和与 total_qty 不一致")

    updates: dict[str, Any] = {}
    if patch.total_qty is not None:
        updates["total_qty"] = patch.total_qty
    if patch.country_breakdown is not None:
        updates["country_breakdown"] = patch.country_breakdown
    if patch.warehouse_breakdown is not None:
        updates["warehouse_breakdown"] = patch.warehouse_breakdown
    if patch.country_breakdown is not None or patch.warehouse_breakdown is not None:
        updates["allocation_snapshot"] = None
    if patch.t_purchase is not None:
        updates["t_purchase"] = patch.t_purchase
    if patch.t_ship is not None:
        updates["t_ship"] = patch.t_ship

    effective_country_breakdown = (
        patch.country_breakdown
        if patch.country_breakdown is not None
        else (item.country_breakdown or {})
    )
    effective_t_purchase = (
        patch.t_purchase if patch.t_purchase is not None else (item.t_purchase or {})
    )
    effective_t_ship = patch.t_ship if patch.t_ship is not None else (item.t_ship or {})

    missing_purchase = missing_timing_countries(effective_country_breakdown, effective_t_purchase)
    if missing_purchase:
        raise ValidationFailed(f"以下采购国家缺少 t_purchase: {', '.join(missing_purchase)}")

    missing_ship = missing_timing_countries(effective_country_breakdown, effective_t_ship)
    if missing_ship:
        raise ValidationFailed(f"以下采购国家缺少 t_ship: {', '.join(missing_ship)}")

    # H3:重新计算 urgent(与 engine/step6_timing 共享同一规则)
    if (
        patch.t_purchase is not None
        or patch.total_qty is not None
        or patch.country_breakdown is not None
    ):
        try:
            updates["urgent"] = has_urgent_purchase(
                effective_t_purchase,
                today=now_beijing().date(),
                countries=positive_qty_countries(effective_country_breakdown),
            )
        except (ValueError, TypeError) as exc:
            raise ValidationFailed(f"t_purchase 包含无效日期: {exc}") from exc

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
        raise ConflictError(f"建议单状态为 {sug.status},不可推送")

    items = (
        (
            await db.execute(
                select(SuggestionItem).where(
                    SuggestionItem.id.in_(req.item_ids),
                    SuggestionItem.suggestion_id == suggestion_id,
                )
            )
        )
        .scalars()
        .all()
    )
    if len(items) != len(req.item_ids):
        raise NotFound("部分条目不存在")

    blocked = [it.id for it in items if it.push_blocker]
    if blocked:
        raise PushBlockedError(
            f"以下条目带有 push_blocker,无法推送: {blocked}",
            detail={"blocked_item_ids": blocked},
        )

    # 入队 push_saihu 任务
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


# ==================== helpers ====================
async def _build_detail(db: AsyncSession, sug: Suggestion) -> SuggestionDetailOut:
    """加载建议单详情。

    一次性批量 JOIN `product_listing` 拉取 commodity_name / main_image,
    避免按条目逐个查询(N+1)。同时不使用进程级缓存--确保同步后
    的 listing 更新能立即在 UI 反映。
    """
    items = (
        (
            await db.execute(
                select(SuggestionItem)
                .where(SuggestionItem.suggestion_id == sug.id)
                .order_by(SuggestionItem.urgent.desc(), SuggestionItem.id)
            )
        )
        .scalars()
        .all()
    )

    # 批量加载本批次涉及的 commodity_sku 对应的产品展示信息
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
            # 同一 sku 可能有多条 listing(不同店铺/站点),取第一个命中
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
    """单条目 enrich(用于 PATCH 返回值)。"""
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
