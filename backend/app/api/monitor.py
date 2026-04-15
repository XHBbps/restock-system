"""监控 API:接口调用日志聚合。"""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel
from sqlalchemy import case, exists, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    UserContext,
    db_session,
    db_session_readonly,
    get_current_user,
    require_permission,
)
from app.core.exceptions import NotFound
from app.core.logging import get_logger
from app.core.permissions import MONITOR_VIEW, SYNC_OPERATE
from app.core.timezone import now_beijing
from app.models.api_call_log import ApiCallLog
from app.models.order import OrderDetailFetchLog, OrderHeader, OrderItem
from app.models.product_listing import ProductListing
from app.tasks.queue import enqueue_task

router = APIRouter(prefix="/api/monitor", tags=["monitor"])
logger = get_logger(__name__)


def _matched_order_detail_exists():
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
    last_call_per_endpoint: dict[str, ApiCallLog] = {}
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
            last_call_per_endpoint[r[0]] = r  # type: ignore[assignment]

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
        stmt = stmt.where(ApiCallLog.saihu_code != 0)
    rows = (await db.execute(stmt)).scalars().all()
    return [RecentCallOut.model_validate(r) for r in rows]


_ENDPOINT_TO_JOB = {
    "/api/order/api/product/pageList.json": "sync_product_listing",
    "/api/warehouseManage/warehouseList.json": "sync_warehouse",
    "/api/warehouseManage/warehouseItemList.json": "sync_inventory",
    "/api/warehouseInOut/outRecords.json": "sync_out_records",
    "/api/order/pageList.json": "sync_order_list",
    "/api/order/detailByOrderId.json": "sync_order_detail",
    "/api/shop/pageList.json": "sync_shop",
}


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
    job_name = _ENDPOINT_TO_JOB.get(row.endpoint)
    if not job_name:
        return {"task_id": None, "message": f"不支持自动重试该接口: {row.endpoint}"}
    task_id, existing = await enqueue_task(db, job_name=job_name, trigger_source="manual")
    return {"task_id": task_id, "existing": existing}
