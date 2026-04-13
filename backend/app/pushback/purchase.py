"""推送选中条目至赛狐生成采购单。

策略(FR-027/045/046):
- 选中条目合并为一张采购单(包含多个 items)
- 每条 item 自动重试 3 次(FR-046)
- 整批结果写回 suggestion_item 状态
- 更新 suggestion 计数
"""

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.core.exceptions import (
    PushBlockedError,
    SaihuAPIError,
    SaihuRateLimited,
)
from app.core.logging import get_logger
from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.models.global_config import GlobalConfig
from app.models.suggestion import Suggestion, SuggestionItem
from app.saihu.endpoints.purchase_create import create_purchase_order
from app.tasks.jobs import JobContext, register

logger = get_logger(__name__)


@register("push_saihu")
async def push_saihu_job(ctx: JobContext) -> None:
    """推送 push_saihu 任务执行入口。"""
    suggestion_id = int(ctx.payload.get("suggestion_id") or 0)
    item_ids = list(ctx.payload.get("item_ids") or [])
    if not suggestion_id or not item_ids:
        raise ValueError("payload 缺少 suggestion_id 或 item_ids")

    await ctx.progress(current_step="准备推送", step_detail=f"{len(item_ids)} 条", total_steps=3)

    # 加载配置 + 条目
    async with async_session_factory() as db:
        config = (await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))).scalar_one()
        if not config.default_purchase_warehouse_id:
            raise ValueError("global_config.default_purchase_warehouse_id 未配置")
        suggestion = (
            await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
        ).scalar_one_or_none()
        if suggestion is None:
            raise ValueError(f"建议单 {suggestion_id} 不存在")
        if suggestion.status == "archived":
            raise PushBlockedError(f"建议单 {suggestion_id} 已归档,不可继续推送")

        items = (
            (
                await db.execute(
                    select(SuggestionItem).where(
                        SuggestionItem.id.in_(item_ids),
                        SuggestionItem.suggestion_id == suggestion_id,
                    )
                )
            )
            .scalars()
            .all()
        )

    if not items:
        raise ValueError("未找到选中的建议条目")

    already_pushed = [it.id for it in items if it.push_status == "pushed"]
    if already_pushed:
        raise PushBlockedError(f"以下条目已推送,不可重复推送: {already_pushed}")

    # 校验全部带 commodity_id(push_blocker 应该已在 API 层过滤)
    blocked = [it.id for it in items if it.push_blocker or not it.commodity_id]
    if blocked:
        raise PushBlockedError(f"以下条目无法推送: {blocked}")
    zero_qty = [it.id for it in items if (it.total_qty or 0) <= 0]
    if zero_qty:
        raise PushBlockedError(f"以下条目 total_qty<=0,无法推送: {zero_qty}")

    await ctx.progress(current_step="调用赛狐采购单创建")

    # 构造 items
    saihu_items = [
        {"commodityId": it.commodity_id, "num": str(it.total_qty)}
        for it in items
    ]

    success = False
    saihu_response: list[dict[str, Any]] = []
    last_error: str | None = None

    settings = get_settings()
    retries = settings.push_auto_retry_times

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(max(retries, 1)),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((SaihuRateLimited,)),
            reraise=True,
        ):
            with attempt:
                saihu_response = await create_purchase_order(
                    warehouse_id=config.default_purchase_warehouse_id,
                    items=saihu_items,
                    include_tax=config.include_tax,
                    action="1",
                    custom_purchase_no=_make_custom_purchase_no(suggestion_id, ctx.task_id),
                )
                success = True
    except SaihuAPIError as exc:
        last_error = f"{exc.code}: {exc.message}" if exc.code else str(exc.message)
        logger.exception("push_saihu_failed", suggestion_id=suggestion_id, error=last_error)

    await ctx.progress(current_step="写回结果")

    # 更新 suggestion_item
    po_number = _join_purchase_order_numbers(saihu_response) if success else None

    pushed_at = now_beijing()
    async with async_session_factory() as db:
        if success:
            # 防 TOCTOU：仅更新尚未被推送的条目（防重复提交窗口内的竞态覆盖）
            await db.execute(
                update(SuggestionItem)
                .where(
                    SuggestionItem.id.in_(item_ids),
                    SuggestionItem.push_status != "pushed",
                )
                .values(
                    push_status="pushed",
                    saihu_po_number=po_number,
                    push_error=None,
                    push_attempt_count=SuggestionItem.push_attempt_count + 1,
                    pushed_at=pushed_at,
                )
            )
        else:
            # P0-4: 防止失败覆盖已成功的 push_status
            await db.execute(
                update(SuggestionItem)
                .where(
                    SuggestionItem.id.in_(item_ids),
                    SuggestionItem.push_status != "pushed",
                )
                .values(
                    push_status="push_failed",
                    push_error=last_error,
                    push_attempt_count=SuggestionItem.push_attempt_count + 1,
                )
            )
        await db.commit()

        # 更新 suggestion 计数 + 状态
        await _refresh_suggestion_counts(db, suggestion_id)
        await db.commit()

    summary = (
        f"成功推送 {len(item_ids)} 条 -> 采购单号 {po_number}"
        if success
        else f"推送失败:{last_error}"
    )
    await ctx.progress(current_step="完成", step_detail=summary)
    if not success:
        raise SaihuAPIError(last_error or "推送失败")


async def _refresh_suggestion_counts(db: AsyncSession, suggestion_id: int) -> None:
    suggestion = (
        await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    ).scalar_one_or_none()
    if suggestion is None:
        raise ValueError(f"建议单 {suggestion_id} 不存在")

    items = (
        (
            await db.execute(
                select(SuggestionItem.push_status).where(
                    SuggestionItem.suggestion_id == suggestion_id
                )
            )
        )
        .scalars()
        .all()
    )
    total = len(items)
    pushed = sum(1 for s in items if s == "pushed")
    failed = sum(1 for s in items if s == "push_failed")

    if suggestion.status == "archived":
        new_status = "archived"
    elif pushed == 0:
        new_status = "draft"
    elif pushed < total:
        new_status = "partial"
    else:
        new_status = "pushed"

    await db.execute(
        update(Suggestion)
        .where(Suggestion.id == suggestion_id)
        .values(
            total_items=total,
            pushed_items=pushed,
            failed_items=failed,
            status=new_status,
        )
    )


def _join_purchase_order_numbers(rows: list[dict[str, Any]]) -> str | None:
    numbers: list[str] = []
    seen: set[str] = set()
    for row in rows:
        raw = row.get("purchaseOrderNo")
        if raw is None:
            continue
        value = str(raw).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        numbers.append(value)
    return ",".join(numbers) if numbers else None


def _make_custom_purchase_no(suggestion_id: int, task_id: int) -> str:
    return f"RS-{suggestion_id}-{task_id}"
