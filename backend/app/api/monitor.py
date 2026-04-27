"""监控 API:接口调用日志聚合。"""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel
from sqlalchemy import case, exists, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    UserContext,
    db_session,
    db_session_readonly,
    get_current_user,
    require_permission,
)
from app.core.exceptions import NotFound, ValidationFailed
from app.core.logging import get_logger
from app.core.permissions import MONITOR_VIEW, SYNC_OPERATE
from app.core.timezone import now_beijing
from app.models.api_call_log import ApiCallLog
from app.models.order import OrderDetailFetchLog, OrderHeader, OrderItem
from app.models.product_listing import ProductListing
from app.tasks.jobs.api_call_retry import (
    JOB_NAME as RETRY_FAILED_API_CALLS_JOB_NAME,
)
from app.tasks.jobs.api_call_retry import (
    MAX_AUTO_RETRY_ATTEMPTS,
)
from app.tasks.queue import enqueue_task

router = APIRouter(prefix="/api/monitor", tags=["monitor"])
logger = get_logger(__name__)


def _matched_order_detail_exists() -> Any:
    return exists(
        select(1)
        .select_from(OrderItem)
        .join(
            ProductListing,
            (ProductListing.shop_id == OrderHeader.shop_id)
            & (ProductListing.seller_sku == OrderItem.seller_sku),
        )
        .where(OrderItem.order_id == OrderHeader.id)
        .where(ProductListing.is_matched.is_(True))
        .where(ProductListing.seller_sku.is_not(None))
    )


# ============================================================
# Saihu API call monitoring
# ============================================================
class EndpointStats(BaseModel):
    endpoint: str
    total_calls: int
    success_count: int
    failed_count: int
    success_rate: float
    last_called_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None


class ApiCallsOverview(BaseModel):
    endpoints: list[EndpointStats]
    postal_compliance_warning: int  # 60 天合规计数(FR-004 + analyze U4)


@router.get("/api-calls", response_model=ApiCallsOverview)
async def get_api_calls(
    hours: int = Query(default=24, ge=1, le=720),
    db: AsyncSession = Depends(db_session_readonly),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(MONITOR_VIEW)),
) -> ApiCallsOverview:
    since = now_beijing() - timedelta(hours=hours)

    rows = (
        await db.execute(
            select(
                ApiCallLog.endpoint,
                func.count().label("total"),
                func.sum(case((ApiCallLog.saihu_code == 0, 1), else_=0)).label("succ"),
                func.max(ApiCallLog.called_at).label("last_at"),
            )
            .where(ApiCallLog.called_at >= since)
            .group_by(ApiCallLog.endpoint)
            .order_by(ApiCallLog.endpoint)
        )
    ).all()

    # 每个 endpoint 取最后一次记录(含错误信息)
    # raw SQL (text) 返回 Row[tuple[endpoint, saihu_code, saihu_msg, error_type]]，
    # 不是 ApiCallLog ORM 实例；显式 tuple 类型避免 mypy 把下标访问当 ORM 属性访问
    # （类型和 # type: ignore[assignment] 一并移除）。
    last_call_per_endpoint: dict[str, tuple[str, int, str | None, str | None]] = {}
    if rows:
        endpoint_names = [r[0] for r in rows]
        last_rows = (
            await db.execute(
                text(
                    """
                    SELECT DISTINCT ON (endpoint)
                        endpoint, saihu_code, saihu_msg, error_type
                    FROM api_call_log
                    WHERE endpoint = ANY(:endpoints) AND called_at >= :since
                    ORDER BY endpoint, called_at DESC
                    """
                ),
                {"endpoints": endpoint_names, "since": since},
            )
        ).all()
        for r in last_rows:
            last_call_per_endpoint[r[0]] = (r[0], int(r[1] or 0), r[2], r[3])

    endpoints = []
    for endpoint, total, succ, last_at in rows:
        total_int = int(total or 0)
        succ_int = int(succ or 0)
        failed = total_int - succ_int
        rate = (succ_int / total_int) if total_int else 0.0
        last = last_call_per_endpoint.get(endpoint)
        last_status = "success" if last and last[1] == 0 else "failed"
        last_error = (last[2] if last else None) if last_status == "failed" else None
        endpoints.append(
            EndpointStats(
                endpoint=endpoint,
                total_calls=total_int,
                success_count=succ_int,
                failed_count=failed,
                success_rate=rate,
                last_called_at=last_at,
                last_status=last_status,
                last_error=last_error,
            )
        )

    # FR-004 合规监测:> 50 天 且 已配对 SKU 相关 且 未拉过详情
    cutoff = now_beijing() - timedelta(days=50)
    compliance_warning = (
        await db.execute(
            select(func.count())
            .select_from(OrderHeader)
            .outerjoin(
                OrderDetailFetchLog,
                (OrderDetailFetchLog.shop_id == OrderHeader.shop_id)
                & (OrderDetailFetchLog.amazon_order_id == OrderHeader.amazon_order_id),
            )
            .where(OrderHeader.purchase_date < cutoff)
            .where(OrderDetailFetchLog.amazon_order_id.is_(None))
            .where(_matched_order_detail_exists())
        )
    ).scalar_one()

    return ApiCallsOverview(
        endpoints=endpoints,
        postal_compliance_warning=int(compliance_warning or 0),
    )


class RecentCallOut(BaseModel):
    id: int
    endpoint: str
    called_at: datetime
    duration_ms: int | None = None
    http_status: int | None = None
    saihu_code: int | None = None
    saihu_msg: str | None = None
    error_type: str | None = None
    retry_status: str | None = None
    auto_retry_attempts: int = 0
    next_retry_at: datetime | None = None
    resolved_at: datetime | None = None
    last_retry_error: str | None = None
    retry_source_log_id: int | None = None
    has_request_payload: bool = False
    can_retry: bool = False

    model_config = {"from_attributes": True}


@router.get("/api-calls/recent", response_model=list[RecentCallOut])
async def get_recent_calls(
    endpoint: str | None = Query(default=None),
    only_failed: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(db_session_readonly),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(MONITOR_VIEW)),
) -> list[RecentCallOut]:
    stmt = select(ApiCallLog).order_by(ApiCallLog.called_at.desc()).limit(limit)
    if endpoint:
        stmt = stmt.where(ApiCallLog.endpoint == endpoint)
    if only_failed:
        stmt = (
            stmt.where(ApiCallLog.saihu_code != 0)
            .where(or_(ApiCallLog.retry_status.is_(None), ApiCallLog.retry_status != "resolved"))
            .where(ApiCallLog.retry_source_log_id.is_(None))
        )
    rows = (await db.execute(stmt)).scalars().all()
    return [_recent_call_out(r) for r in rows]


def _recent_call_out(row: ApiCallLog) -> RecentCallOut:
    return RecentCallOut(
        id=row.id,
        endpoint=row.endpoint,
        called_at=row.called_at,
        duration_ms=row.duration_ms,
        http_status=row.http_status,
        saihu_code=row.saihu_code,
        saihu_msg=row.saihu_msg,
        error_type=row.error_type,
        retry_status=row.retry_status,
        auto_retry_attempts=row.auto_retry_attempts,
        next_retry_at=row.next_retry_at,
        resolved_at=row.resolved_at,
        last_retry_error=row.last_retry_error,
        retry_source_log_id=row.retry_source_log_id,
        has_request_payload=row.request_payload is not None,
        can_retry=_can_retry(row),
    )


def _can_retry(row: ApiCallLog) -> bool:
    return (
        row.saihu_code == 40019
        and row.request_payload is not None
        and row.retry_source_log_id is None
        and row.retry_status not in {"resolved", "permanent", "unsupported"}
        and row.auto_retry_attempts < MAX_AUTO_RETRY_ATTEMPTS
    )


@router.post("/api-calls/{call_id}/retry")
async def retry_call(
    call_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(SYNC_OPERATE)),
) -> dict[str, Any]:
    row = (
        await db.execute(select(ApiCallLog).where(ApiCallLog.id == call_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(f"调用记录 {call_id} 不存在")
    if row.retry_status == "resolved":
        raise ValidationFailed("该失败调用已经解决，无需重试")
    if row.retry_status == "permanent":
        raise ValidationFailed("该失败调用已达到重试上限或失败类型不可恢复")
    if row.retry_status == "unsupported" or row.request_payload is None:
        raise ValidationFailed("该调用日志缺少原始请求参数，无法精确重试")
    if row.saihu_code != 40019:
        raise ValidationFailed("仅支持重试赛狐返回码 40019 的失败调用")
    if row.retry_source_log_id is not None:
        raise ValidationFailed("自动重试产生的子日志不能再次作为重试源")
    if row.auto_retry_attempts >= MAX_AUTO_RETRY_ATTEMPTS:
        raise ValidationFailed("该失败调用已达到最多 5 次重试上限")

    row.retry_status = "queued"
    row.next_retry_at = now_beijing()
    await db.flush()
    task_id, existing = await enqueue_task(
        db,
        job_name=RETRY_FAILED_API_CALLS_JOB_NAME,
        trigger_source="manual",
        payload={"call_ids": [call_id]},
        priority=50,
    )
    return {"task_id": task_id, "existing": existing}
