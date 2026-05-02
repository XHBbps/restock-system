"""Precise retry queue for Saihu 40019 API call logs."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import func, or_, select, update

from app.core.exceptions import SaihuAPIError, SaihuRateLimited
from app.core.logging import get_logger
from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.models.api_call_log import ApiCallLog
from app.models.task_run import TaskRun
from app.saihu.client import get_saihu_client
from app.saihu.rate_limit import get_endpoint_qps
from app.tasks.jobs import JobContext, register

logger = get_logger(__name__)

JOB_NAME = "retry_failed_api_calls"
MAX_AUTO_RETRY_ATTEMPTS = 5
DEFAULT_BATCH_SIZE = 50
SUPPORTED_ENDPOINT_JOBS: dict[str, tuple[str, ...]] = {
    "/api/commodity/pageList.json": ("sync_product_listing",),
    "/api/order/api/product/pageList.json": ("sync_product_listing",),
    "/api/warehouseManage/warehouseList.json": ("sync_warehouse",),
    "/api/warehouseManage/warehouseItemList.json": ("sync_inventory",),
    "/api/warehouseInOut/outRecords.json": ("sync_out_records",),
    "/api/order/pageList.json": ("sync_order_list",),
    "/api/multiplatform/order/list.json": ("sync_order_list",),
    "/api/order/detailByOrderId.json": ("sync_order_detail", "refetch_order_detail"),
    "/api/shop/pageList.json": ("sync_shop",),
}


@register(JOB_NAME)
async def retry_failed_api_calls_job(ctx: JobContext) -> None:
    call_ids = _payload_call_ids(ctx.payload)
    candidates = await _load_retry_candidates(call_ids=call_ids)
    total = len(candidates)
    await ctx.progress(current_step="重试赛狐 40019 失败调用", total_steps=total or None)

    retried = 0
    skipped_busy = 0
    skipped_invalid = 0
    for index, row in enumerate(candidates, start=1):
        if not _is_retryable_row(row):
            skipped_invalid += 1
            continue
        if await _has_active_related_task(row.endpoint):
            skipped_busy += 1
            await ctx.progress(
                step_detail=f"已处理 {index} / 总数 {total}，跳过忙碌 {skipped_busy}",
                total_steps=total or None,
            )
            continue

        await asyncio.sleep(retry_interval_seconds(row.endpoint))
        await _retry_one(row)
        retried += 1
        await ctx.progress(
            step_detail=(
                f"已处理 {index} / 总数 {total}，已重试 {retried}，"
                f"跳过忙碌 {skipped_busy}"
            ),
            total_steps=total or None,
        )

    await ctx.progress(
        current_step="完成",
        step_detail=f"重试 {retried}，跳过忙碌 {skipped_busy}，跳过无效 {skipped_invalid}",
        total_steps=total or None,
    )


def retry_interval_seconds(endpoint: str) -> float:
    """Return a conservative replay interval based on the endpoint QPS."""

    return 1.5 / max(get_endpoint_qps(endpoint), 1)


def busy_job_names_for_endpoint(endpoint: str) -> tuple[str, ...]:
    jobs = SUPPORTED_ENDPOINT_JOBS.get(endpoint, ())
    return (*jobs, "sync_all")


def _payload_call_ids(payload: dict[str, Any]) -> list[int] | None:
    raw = payload.get("call_ids")
    if raw is None:
        return None
    if not isinstance(raw, list):
        return []
    ids: list[int] = []
    for value in raw:
        if isinstance(value, int) and value > 0:
            ids.append(value)
    return ids


async def _load_retry_candidates(*, call_ids: list[int] | None = None) -> list[ApiCallLog]:
    async with async_session_factory() as db:
        stmt = (
            select(ApiCallLog)
            .where(ApiCallLog.saihu_code == 40019)
            .where(ApiCallLog.request_payload.is_not(None))
            .where(ApiCallLog.retry_source_log_id.is_(None))
            .where(ApiCallLog.auto_retry_attempts < MAX_AUTO_RETRY_ATTEMPTS)
            .where(or_(ApiCallLog.retry_status.is_(None), ApiCallLog.retry_status == "queued"))
            .order_by(ApiCallLog.called_at.asc(), ApiCallLog.id.asc())
            .limit(DEFAULT_BATCH_SIZE)
        )
        if call_ids is None:
            stmt = stmt.where(ApiCallLog.retry_status == "queued").where(
                or_(ApiCallLog.next_retry_at.is_(None), ApiCallLog.next_retry_at <= now_beijing())
            )
        elif call_ids:
            stmt = stmt.where(ApiCallLog.id.in_(call_ids))
        else:
            return []
        return list((await db.execute(stmt)).scalars().all())


def _is_retryable_row(row: ApiCallLog) -> bool:
    return (
        row.saihu_code == 40019
        and isinstance(row.request_payload, dict)
        and row.retry_source_log_id is None
        and row.retry_status not in {"resolved", "permanent", "unsupported"}
        and row.auto_retry_attempts < MAX_AUTO_RETRY_ATTEMPTS
    )


async def _has_active_related_task(endpoint: str) -> bool:
    job_names = busy_job_names_for_endpoint(endpoint)
    if not job_names:
        return False
    async with async_session_factory() as db:
        count = (
            await db.execute(
                select(func.count())
                .select_from(TaskRun)
                .where(TaskRun.status.in_(("pending", "running")))
                .where(TaskRun.job_name.in_(job_names))
            )
        ).scalar_one()
    return int(count or 0) > 0


async def _retry_one(row: ApiCallLog) -> None:
    payload = dict(row.request_payload or {})
    client = get_saihu_client()
    try:
        await client.post(
            row.endpoint,
            payload,
            retry_source_log_id=row.id,
            queue_rate_limit_retry=False,
        )
    except SaihuRateLimited as exc:
        await _mark_retry_rate_limited(row, str(exc))
    except SaihuAPIError as exc:
        await _mark_permanent(row, _format_retry_error(exc))
    except Exception as exc:
        await _mark_permanent(row, str(exc))
    else:
        await _mark_resolved(row)


async def _mark_resolved(row: ApiCallLog) -> None:
    async with async_session_factory() as db:
        await db.execute(
            update(ApiCallLog)
            .where(ApiCallLog.id == row.id)
            .values(
                retry_status="resolved",
                auto_retry_attempts=ApiCallLog.auto_retry_attempts + 1,
                resolved_at=now_beijing(),
                last_retry_error=None,
                next_retry_at=None,
            )
        )
        await db.commit()


async def _mark_retry_rate_limited(row: ApiCallLog, error: str) -> None:
    next_attempt = row.auto_retry_attempts + 1
    async with async_session_factory() as db:
        await db.execute(
            update(ApiCallLog)
            .where(ApiCallLog.id == row.id)
            .values(
                retry_status="permanent" if next_attempt >= MAX_AUTO_RETRY_ATTEMPTS else "queued",
                auto_retry_attempts=ApiCallLog.auto_retry_attempts + 1,
                next_retry_at=None if next_attempt >= MAX_AUTO_RETRY_ATTEMPTS else now_beijing(),
                last_retry_error=error[:2000],
            )
        )
        await db.commit()


async def _mark_permanent(row: ApiCallLog, error: str) -> None:
    async with async_session_factory() as db:
        await db.execute(
            update(ApiCallLog)
            .where(ApiCallLog.id == row.id)
            .values(
                retry_status="permanent",
                auto_retry_attempts=ApiCallLog.auto_retry_attempts + 1,
                next_retry_at=None,
                last_retry_error=error[:2000],
            )
        )
        await db.commit()


def _format_retry_error(exc: SaihuAPIError) -> str:
    parts = [exc.message]
    if exc.code is not None:
        parts.append(f"code={exc.code}")
    if exc.request_id:
        parts.append(f"request_id={exc.request_id}")
    return " ".join(parts)
