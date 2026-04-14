"""Dashboard snapshot refresh job."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.api.metrics import REFRESH_DASHBOARD_JOB_NAME, build_dashboard_payload
from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.models.dashboard_snapshot import DashboardSnapshot
from app.tasks.jobs import JobContext, register


async def _mark_refreshing() -> None:
    now = now_beijing()
    async with async_session_factory() as db:
        stmt = pg_insert(DashboardSnapshot).values(
            id=1,
            status="refreshing",
            refresh_started_at=now,
            refresh_finished_at=None,
            last_refresh_error=None,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[DashboardSnapshot.id],
            set_={
                "status": "refreshing",
                "refresh_started_at": now,
                "refresh_finished_at": None,
                "last_refresh_error": None,
                "updated_at": now,
            },
        )
        await db.execute(stmt)
        await db.commit()


async def _mark_ready(payload: dict) -> None:
    now = now_beijing()
    async with async_session_factory() as db:
        stmt = pg_insert(DashboardSnapshot).values(
            id=1,
            status="ready",
            payload=payload,
            refreshed_at=now,
            refresh_finished_at=now,
            last_refresh_error=None,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[DashboardSnapshot.id],
            set_={
                "status": "ready",
                "payload": payload,
                "refreshed_at": now,
                "refresh_finished_at": now,
                "last_refresh_error": None,
                "updated_at": now,
            },
        )
        await db.execute(stmt)
        await db.commit()


async def _mark_failed(error: str) -> None:
    now = now_beijing()
    async with async_session_factory() as db:
        row = (
            await db.execute(
                select(DashboardSnapshot.payload).where(DashboardSnapshot.id == 1)
            )
        ).first()
        has_payload = bool(row and row[0])
        stmt = pg_insert(DashboardSnapshot).values(
            id=1,
            status="ready" if has_payload else "failed",
            last_refresh_error=error[:5000],
            refresh_finished_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[DashboardSnapshot.id],
            set_={
                "status": "ready" if has_payload else "failed",
                "last_refresh_error": error[:5000],
                "refresh_finished_at": now,
                "updated_at": now,
            },
        )
        await db.execute(stmt)
        await db.commit()


@register(REFRESH_DASHBOARD_JOB_NAME)
async def refresh_dashboard_snapshot_job(ctx: JobContext) -> None:
    await _mark_refreshing()
    await ctx.progress(current_step="Step 1: 计算信息总览快照", total_steps=2)
    try:
        async with async_session_factory() as db:
            payload = await build_dashboard_payload(db)
        await ctx.progress(current_step="Step 2: 写入信息总览快照")
        await _mark_ready(payload.model_dump())
        await ctx.progress(step_detail="信息总览快照已更新")
    except Exception as exc:
        await _mark_failed(str(exc))
        raise
