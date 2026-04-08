"""calc_engine 任务注册。"""

from app.engine.runner import run_engine
from app.tasks.jobs import JobContext, register


@register("calc_engine")
async def calc_engine_job(ctx: JobContext) -> None:
    triggered_by = ctx.payload.get("triggered_by", "scheduler")
    suggestion_id = await run_engine(ctx, triggered_by=str(triggered_by))
    await ctx.progress(step_detail=f"建议单 id = {suggestion_id}")
