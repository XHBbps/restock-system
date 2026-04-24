"""Manual sync and engine trigger API."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import UserContext, db_session, get_current_user, require_permission
from app.core.permissions import RESTOCK_OPERATE, SYNC_OPERATE, SYNC_VIEW
from app.models.global_config import GlobalConfig
from app.models.task_run import TaskRun
from app.schemas.sync import (
    EngineRunIn,
    OrderDetailRefetchIn,
    OrderDetailRefetchOut,
    SchedulerStatusOut,
    SchedulerToggleIn,
)
from app.sync.order_detail import (
    DEFAULT_REFETCH_DAYS,
    REFETCH_JOB_NAME,
    find_refetch_targets,
    serialize_refetch_targets,
)
from app.tasks.queue import enqueue_task
from app.tasks.scheduler import reload_scheduler, scheduler_status

router = APIRouter(prefix="/api", tags=["sync"])
ORDER_DETAIL_ACTIVE_JOB_NAMES = (REFETCH_JOB_NAME, "sync_order_detail", "sync_all")
ORDER_DETAIL_ACTIVE_JOB_PRIORITY = {
    REFETCH_JOB_NAME: 0,
    "sync_order_detail": 1,
    "sync_all": 2,
}


async def _enqueue(db: AsyncSession, job_name: str) -> dict[str, Any]:
    task_id, existing = await enqueue_task(db, job_name=job_name, trigger_source="manual")
    return {"task_id": task_id, "existing": existing}


async def _get_active_order_detail_task(db: AsyncSession) -> TaskRun | None:
    priority_order = case(
        *[
            (TaskRun.job_name == job_name, priority)
            for job_name, priority in ORDER_DETAIL_ACTIVE_JOB_PRIORITY.items()
        ],
        else_=999,
    )
    result = await db.execute(
        select(TaskRun)
        .where(TaskRun.status.in_(("pending", "running")))
        .where(TaskRun.job_name.in_(ORDER_DETAIL_ACTIVE_JOB_NAMES))
        .order_by(priority_order.asc(), TaskRun.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.post("/sync/all")
async def sync_all(
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(SYNC_OPERATE)),
) -> dict[str, Any]:
    return await _enqueue(db, "sync_all")


@router.post("/sync/shop")
async def sync_shop(
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(SYNC_OPERATE)),
) -> dict[str, Any]:
    return await _enqueue(db, "sync_shop")


@router.post("/sync/product-listing")
async def sync_product_listing(
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(SYNC_OPERATE)),
) -> dict[str, Any]:
    return await _enqueue(db, "sync_product_listing")


@router.post("/sync/inventory")
async def sync_inventory(
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(SYNC_OPERATE)),
) -> dict[str, Any]:
    return await _enqueue(db, "sync_inventory")


@router.post("/sync/out-records")
async def sync_out_records(
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(SYNC_OPERATE)),
) -> dict[str, Any]:
    return await _enqueue(db, "sync_out_records")


@router.post("/sync/orders")
async def sync_orders(
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(SYNC_OPERATE)),
) -> dict[str, Any]:
    return await _enqueue(db, "sync_order_list")


@router.post("/sync/warehouse")
async def sync_warehouse(
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(SYNC_OPERATE)),
) -> dict[str, Any]:
    return await _enqueue(db, "sync_warehouse")


@router.post("/sync/order-detail/refetch", response_model=OrderDetailRefetchOut)
async def refetch_order_detail(
    payload: OrderDetailRefetchIn,
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(SYNC_OPERATE)),
) -> OrderDetailRefetchOut:
    days = payload.days or DEFAULT_REFETCH_DAYS
    active_task = await _get_active_order_detail_task(db)
    if active_task is not None:
        return OrderDetailRefetchOut(
            task_id=active_task.id,
            existing=True,
            matched_count=0,
            queued_count=0,
            active_job_name=active_task.job_name,
            active_trigger_source=active_task.trigger_source,
        )

    targets = await find_refetch_targets(
        db,
        days=days,
        shop_id=payload.shop_id,
    )
    matched_count = len(targets)

    if matched_count == 0:
        return OrderDetailRefetchOut(
            task_id=None,
            existing=False,
            matched_count=0,
            queued_count=0,
            active_job_name=None,
            active_trigger_source=None,
        )

    task_id, existing = await enqueue_task(
        db,
        job_name=REFETCH_JOB_NAME,
        trigger_source="manual",
        dedupe_key=REFETCH_JOB_NAME,
        payload={
            "days": days,
            "shop_id": payload.shop_id,
            "targets": serialize_refetch_targets(targets),
        },
    )
    return OrderDetailRefetchOut(
        task_id=task_id,
        existing=existing,
        matched_count=matched_count,
        queued_count=0 if existing else matched_count,
        active_job_name=REFETCH_JOB_NAME if existing else None,
        active_trigger_source="manual" if existing else None,
    )


@router.get("/sync/scheduler", response_model=SchedulerStatusOut)
async def get_scheduler_status(
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(SYNC_VIEW)),
) -> SchedulerStatusOut:
    return await scheduler_status()


@router.post("/sync/scheduler", response_model=SchedulerStatusOut)
async def set_scheduler_status(
    payload: SchedulerToggleIn,
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(SYNC_OPERATE)),
) -> SchedulerStatusOut:
    await db.execute(
        update(GlobalConfig).where(GlobalConfig.id == 1).values(scheduler_enabled=payload.enabled)
    )
    await db.commit()
    return await reload_scheduler()


@router.post("/engine/run")
async def run_engine_now(
    payload: EngineRunIn,
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(RESTOCK_OPERATE)),
) -> dict[str, Any]:
    task_id, existing = await enqueue_task(
        db,
        job_name="calc_engine",
        trigger_source="manual",
        payload={"triggered_by": "manual", "demand_date": payload.demand_date.isoformat()},
    )
    return {"task_id": task_id, "existing": existing}
