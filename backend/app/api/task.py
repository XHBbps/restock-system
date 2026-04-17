"""TaskRun REST API."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, db_session_readonly, get_current_permissions
from app.core.exceptions import ConflictError, NotFound
from app.models.task_run import TaskRun
from app.tasks.access import (
    MANUAL_ENQUEUE_JOB_NAMES,
    TASK_MANAGE_PERMISSIONS,
    TASK_VIEW_PERMISSIONS,
    ensure_task_access,
    visible_task_job_names,
)
from app.tasks.queue import enqueue_task

router = APIRouter(prefix="/api/tasks", tags=["task"])


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
    dedupe_key: str | None = Field(default=None, description="Optional; defaults to job_name")


class EnqueueResponse(BaseModel):
    task_id: int
    existing: bool


@router.get("", response_model=TaskListOut)
async def list_tasks(
    job_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(db_session_readonly),
    permissions: frozenset[str] = Depends(get_current_permissions),
) -> TaskListOut:
    visible_jobs = visible_task_job_names(permissions)
    if not visible_jobs or (job_name is not None and job_name not in visible_jobs):
        return TaskListOut(items=[], total=0)

    base = select(TaskRun).where(TaskRun.job_name.in_(sorted(visible_jobs)))
    if job_name:
        base = base.where(TaskRun.job_name == job_name)
    if status:
        base = base.where(TaskRun.status == status)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (await db.execute(base.order_by(TaskRun.created_at.desc()).limit(limit))).scalars().all()
    return TaskListOut(items=[TaskRunOut.model_validate(r) for r in rows], total=total)


@router.post("", response_model=EnqueueResponse)
async def create_task(
    req: EnqueueRequest,
    db: AsyncSession = Depends(db_session),
    permissions: frozenset[str] = Depends(get_current_permissions),
) -> EnqueueResponse:
    if req.job_name not in MANUAL_ENQUEUE_JOB_NAMES:
        raise ConflictError(f"Unknown job_name: {req.job_name}")
    ensure_task_access(req.job_name, permissions, TASK_MANAGE_PERMISSIONS)
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
    db: AsyncSession = Depends(db_session_readonly),
    permissions: frozenset[str] = Depends(get_current_permissions),
) -> TaskRunOut:
    row = (await db.execute(select(TaskRun).where(TaskRun.id == task_id))).scalar_one_or_none()
    if row is None:
        raise NotFound(f"task {task_id} does not exist")
    ensure_task_access(row.job_name, permissions, TASK_VIEW_PERMISSIONS)
    return TaskRunOut.model_validate(row)


@router.post("/{task_id}/cancel", status_code=200)
async def cancel_task(
    task_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    permissions: frozenset[str] = Depends(get_current_permissions),
) -> dict[str, str]:
    row = (await db.execute(select(TaskRun).where(TaskRun.id == task_id))).scalar_one_or_none()
    if row is None:
        raise NotFound(f"task {task_id} does not exist")
    ensure_task_access(row.job_name, permissions, TASK_MANAGE_PERMISSIONS)
    if row.status not in ("pending",):
        raise ConflictError(f"Task status is {row.status}; cannot cancel")
    await db.execute(update(TaskRun).where(TaskRun.id == task_id).values(status="cancelled"))
    return {"status": "cancelled"}
