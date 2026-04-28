"""同步任务通用工具:sync_state 状态记录。"""

from datetime import datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_beijing
from app.models.sync_state import SyncState


async def mark_sync_running(db: AsyncSession, job_name: str) -> datetime:
    now = now_beijing()
    stmt = pg_insert(SyncState).values(job_name=job_name, last_run_at=now, last_status="running")
    stmt = stmt.on_conflict_do_update(
        index_elements=["job_name"],
        set_={"last_run_at": now, "last_status": "running"},
    )
    await db.execute(stmt)
    await db.commit()
    return now


async def mark_sync_success(
    db: AsyncSession,
    job_name: str,
    started: datetime,
    success_at: datetime | None = None,
) -> None:
    success_watermark = success_at or now_beijing()
    stmt = pg_insert(SyncState).values(
        job_name=job_name,
        last_run_at=started,
        last_success_at=success_watermark,
        last_status="success",
        last_error=None,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["job_name"],
        set_={
            "last_run_at": started,
            "last_success_at": success_watermark,
            "last_status": "success",
            "last_error": None,
        },
    )
    await db.execute(stmt)
    await db.commit()


async def mark_sync_failed(db: AsyncSession, job_name: str, error: str) -> None:
    stmt = pg_insert(SyncState).values(
        job_name=job_name, last_status="failed", last_error=error[:5000]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["job_name"],
        set_={"last_status": "failed", "last_error": error[:5000]},
    )
    await db.execute(stmt)
    await db.commit()
