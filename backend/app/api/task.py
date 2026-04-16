"""TaskRun REST API."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, db_session_readonly, get_current_permissions
from app.core.exceptions import ConflictError, Forbidden, NotFound
from app.core.permissions import HOME_REFRESH, RESTOCK_OPERATE, SYNC_OPERATE, SYNC_VIEW
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
    "refetch_order_detail",
    "sync_shop",
    "sync_all",
    "calc_engine",
    "daily_archive",
    "refresh_dashboard_snapshot",
}

TASK_VIEW_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "sync_product_listing": (SYNC_VIEW, SYNC_OPERATE),
    "sync_warehouse": (SYNC_VIEW, SYNC_OPERATE),
    "sync_inventory": (SYNC_VIEW, SYNC_OPERATE),
    "sync_out_records": (SYNC_VIEW, SYNC_OPERATE),
    "sync_order_list": (SYNC_VIEW, SYNC_OPERATE),
    "sync_order_detail": (SYNC_VIEW, SYNC_OPERATE),
    "refetch_order_detail": (SYNC_VIEW, SYNC_OPERATE),
    "sync_shop": (SYNC_VIEW, SYNC_OPERATE),
    "sync_all": (SYNC_VIEW, SYNC_OPERATE),
    "daily_archive": (SYNC_VIEW, SYNC_OPERATE),
    "calc_engine": (RESTOCK_OPERATE,),
    "push_saihu": (RESTOCK_OPERATE,),
    "refresh_dashboard_snapshot": (HOME_REFRESH,),
}

TASK_MANAGE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "sync_product_listing": (SYNC_OPERATE,),
    "sync_warehouse": (SYNC_OPERATE,),
    "sync_inventory": (SYNC_OPERATE,),
    "sync_out_records": (SYNC_OPERATE,),
    "sync_order_list": (SYNC_OPERATE,),
    "sync_order_detail": (SYNC_OPERATE,),
    "refetch_order_detail": (SYNC_OPERATE,),
    "sync_shop": (SYNC_OPERATE,),
    "sync_all": (SYNC_OPERATE,),
    "daily_archive": (SYNC_OPERATE,),
    "calc_engine": (RESTOCK_OPERATE,),
    "push_saihu": (RESTOCK_OPERATE,),
    "refresh_dashboard_snapshot": (HOME_REFRESH,),
}


def _has_any_permission(permissions: frozenset[str], required: tuple[str, ...]) -> bool:
    return any(code in permissions for code in required)


def _visible_job_names(permissions: frozenset[str]) -> set[str]:
    return {
        job_name
        for job_name, required in TASK_VIEW_PERMISSIONS.items()
        if _has_any_permission(permissions, required)
    }


def _ensure_job_access(
    job_name: str,
    permissions: frozenset[str],
    mapping: dict[str, tuple[str, ...]],
) -> None:
    required = mapping.get(job_name)
    if required is None or not _has_any_permission(permissions, required):
        raise Forbidden("Permission denied")


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
    visible_jobs = _visible_job_names(permissions)
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
    if req.job_name not in VALID_JOB_NAMES:
        raise ConflictError(f"Unknown job_name: {req.job_name}")
    _ensure_job_access(req.job_name, permissions, TASK_MANAGE_PERMISSIONS)
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
    _ensure_job_access(row.job_name, permissions, TASK_VIEW_PERMISSIONS)
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
    _ensure_job_access(row.job_name, permissions, TASK_MANAGE_PERMISSIONS)
    if row.status not in ("pending",):
        raise ConflictError(f"Task status is {row.status}; cannot cancel")
    await db.execute(update(TaskRun).where(TaskRun.id == task_id).values(status="cancelled"))
    return {"status": "cancelled"}
