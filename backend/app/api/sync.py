"""手动同步与引擎触发 API（contracts/sync.yaml）。

每个端点把对应任务入队到 task_run，前端通过 task_id 轮询进度。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_session
from app.tasks.queue import enqueue_task

router = APIRouter(prefix="/api", tags=["sync"])


async def _enqueue(db: AsyncSession, job_name: str) -> dict:
    task_id, existing = await enqueue_task(
        db, job_name=job_name, trigger_source="manual"
    )
    return {"task_id": task_id, "existing": existing}


@router.post("/sync/all")
async def sync_all(
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> dict:
    return await _enqueue(db, "sync_all")


@router.post("/sync/product-listing")
async def sync_product_listing(
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> dict:
    return await _enqueue(db, "sync_product_listing")


@router.post("/sync/inventory")
async def sync_inventory(
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> dict:
    return await _enqueue(db, "sync_inventory")


@router.post("/sync/out-records")
async def sync_out_records(
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> dict:
    return await _enqueue(db, "sync_out_records")


@router.post("/sync/orders")
async def sync_orders(
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> dict:
    # 触发列表 + 详情两步（chained 由 worker 顺序执行）
    return await _enqueue(db, "sync_order_list")


@router.post("/sync/warehouse")
async def sync_warehouse(
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> dict:
    return await _enqueue(db, "sync_warehouse")


@router.post("/engine/run")
async def run_engine_now(
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> dict:
    task_id, existing = await enqueue_task(
        db,
        job_name="calc_engine",
        trigger_source="manual",
        payload={"triggered_by": "manual"},
    )
    return {"task_id": task_id, "existing": existing}
