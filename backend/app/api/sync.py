"""Manual sync and engine trigger API."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_session
from app.models.global_config import GlobalConfig
from app.schemas.sync import SchedulerStatusOut, SchedulerToggleIn
from app.tasks.queue import enqueue_task
from app.tasks.scheduler import reload_scheduler, scheduler_status

router = APIRouter(prefix="/api", tags=["sync"])


async def _enqueue(db: AsyncSession, job_name: str) -> dict[str, Any]:
    task_id, existing = await enqueue_task(db, job_name=job_name, trigger_source="manual")
    return {"task_id": task_id, "existing": existing}


@router.post("/sync/all")
async def sync_all(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> dict[str, Any]:
    return await _enqueue(db, "sync_all")


@router.post("/sync/shop")
async def sync_shop(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> dict[str, Any]:
    return await _enqueue(db, "sync_shop")


@router.post("/sync/product-listing")
async def sync_product_listing(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> dict[str, Any]:
    return await _enqueue(db, "sync_product_listing")


@router.post("/sync/inventory")
async def sync_inventory(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> dict[str, Any]:
    return await _enqueue(db, "sync_inventory")


@router.post("/sync/out-records")
async def sync_out_records(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> dict[str, Any]:
    return await _enqueue(db, "sync_out_records")


@router.post("/sync/orders")
async def sync_orders(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> dict[str, Any]:
    return await _enqueue(db, "sync_order_list")


@router.post("/sync/warehouse")
async def sync_warehouse(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> dict[str, Any]:
    return await _enqueue(db, "sync_warehouse")


@router.get("/sync/scheduler", response_model=SchedulerStatusOut)
async def get_scheduler_status(
    _: dict[str, Any] = Depends(get_current_session),
) -> SchedulerStatusOut:
    return await scheduler_status()


@router.post("/sync/scheduler", response_model=SchedulerStatusOut)
async def set_scheduler_status(
    payload: SchedulerToggleIn,
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> SchedulerStatusOut:
    await db.execute(
        update(GlobalConfig).where(GlobalConfig.id == 1).values(scheduler_enabled=payload.enabled)
    )
    await db.commit()
    return await reload_scheduler()


@router.post("/engine/run")
async def run_engine_now(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> dict[str, Any]:
    task_id, existing = await enqueue_task(
        db,
        job_name="calc_engine",
        trigger_source="manual",
        payload={"triggered_by": "manual"},
    )
    return {"task_id": task_id, "existing": existing}
