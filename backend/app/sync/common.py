"""同步任务通用工具：sync_state 状态记录。"""

from datetime import datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_beijing
from app.models.sync_state import SyncState


async def mark_sync_running(db: AsyncSession, job_name: str) -> datetime:
    now = now_beijing()
    await db.execute(
        update(SyncState)
        .where(SyncState.job_name == job_name)
        .values(last_run_at=now, last_status="running")
    )
    await db.commit()
    return now


async def mark_sync_success(db: AsyncSession, job_name: str, started: datetime) -> None:
    await db.execute(
        update(SyncState)
        .where(SyncState.job_name == job_name)
        .values(last_run_at=started, last_success_at=now_beijing(), last_status="success", last_error=None)
    )
    await db.commit()


async def mark_sync_failed(db: AsyncSession, job_name: str, error: str) -> None:
    await db.execute(
        update(SyncState)
        .where(SyncState.job_name == job_name)
        .values(last_status="failed", last_error=error[:5000])
    )
    await db.commit()
