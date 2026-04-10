"""任务系统 REST API(对应 contracts/task.yaml)。"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_session
from app.core.exceptions import ConflictError, NotFound
from app.models.task_run import TaskRun
from app.tasks.queue import enqueue_task

router = APIRouter(prefix="/api/tasks", tags=["task"])

VALID_JOB_NAMES = {
    "sync_product_listing",
    "sync_warehouse",
    "sync_inventory",
    "sync_out_records",
    "sync_order_list",
    "sync_order_detail",
    "sync_shop",
    "sync_all",
    "calc_engine",
    "push_saihu",
    "daily_archive",
}


class TaskRunOut(BaseModel):
    id: int
    job_name: str
    dedupe_key: str
    status: str
    trigger_source: str
    priority: int
    payload: dict[str, Any]
    current_step: str | None = None
    step_detail: str | None = None
    total_steps: int | None = None
    attempt_count: int
    error_msg: str | None = None
    result_summary: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskListOut(BaseModel):
    items: list[TaskRunOut]
    total: int


class EnqueueRequest(BaseModel):
    job_name: str
    payload: dict[str, Any] | None = None
    dedupe_key: str | None = Field(default=None, description="可选,默认 = job_name")


class EnqueueResponse(BaseModel):
    task_id: int
    existing: bool


@router.get("", response_model=TaskListOut)
async def list_tasks(
    job_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> TaskListOut:
    base = select(TaskRun)
    if job_name:
        base = base.where(TaskRun.job_name == job_name)
    if status:
        base = base.where(TaskRun.status == status)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(TaskRun.created_at.desc()).limit(limit))
    ).scalars().all()
    return TaskListOut(items=[TaskRunOut.model_validate(r) for r in rows], total=total)


@router.post("", response_model=EnqueueResponse)
async def create_task(
    req: EnqueueRequest,
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> EnqueueResponse:
    if req.job_name not in VALID_JOB_NAMES:
        raise ConflictError(f"未知的 job_name: {req.job_name}")
    task_id, existing = await enqueue_task(
        db,
        job_name=req.job_name,
        trigger_source="manual",
        dedupe_key=req.dedupe_key,
        payload=req.payload or {},
    )
    return EnqueueResponse(task_id=task_id, existing=existing)


@router.get("/{task_id}", response_model=TaskRunOut)
async def get_task(
    task_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> TaskRunOut:
    row = (await db.execute(select(TaskRun).where(TaskRun.id == task_id))).scalar_one_or_none()
    if row is None:
        raise NotFound(f"task {task_id} 不存在")
    return TaskRunOut.model_validate(row)


@router.post("/{task_id}/cancel", status_code=200)
async def cancel_task(
    task_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> dict[str, str]:
    row = (await db.execute(select(TaskRun).where(TaskRun.id == task_id))).scalar_one_or_none()
    if row is None:
        raise NotFound(f"task {task_id} 不存在")
    if row.status not in ("pending",):
        raise ConflictError(f"任务状态为 {row.status},无法取消")
    await db.execute(update(TaskRun).where(TaskRun.id == task_id).values(status="cancelled"))
    return {"status": "cancelled"}
