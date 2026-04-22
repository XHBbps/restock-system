"""calc_engine task registration."""

from __future__ import annotations

from sqlalchemy import select

from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.engine.runner import run_engine
from app.models.global_config import GlobalConfig
from app.tasks.jobs import JobContext, register


@register("calc_engine")
async def calc_engine_job(ctx: JobContext) -> None:
    triggered_by = ctx.payload.get("triggered_by", "scheduler")
    suggestion_id = await run_engine(ctx, triggered_by=str(triggered_by))
    if suggestion_id is None:
        await ctx.progress(step_detail="no_suggestion_needed")
        return

    async with async_session_factory() as db:
        config = (await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))).scalar_one()
        config.suggestion_generation_enabled = False
        config.generation_toggle_updated_at = now_beijing()
        config.generation_toggle_updated_by = None
        await db.commit()

    await ctx.progress(step_detail=f"建议单 id = {suggestion_id}")
