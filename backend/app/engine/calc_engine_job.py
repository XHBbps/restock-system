"""calc_engine 任务注册。"""

from app.engine.runner import run_engine
from app.tasks.jobs import JobContext, register


@register("calc_engine")
async def calc_engine_job(ctx: JobContext) -> None:
    triggered_by = ctx.payload.get("triggered_by", "scheduler")
    suggestion_id = await run_engine(ctx, triggered_by=str(triggered_by))
    if suggestion_id is None:
        await ctx.progress(step_detail="无启用 SKU，未生成建议单")
    else:
        await ctx.progress(step_detail=f"建议单 id = {suggestion_id}")
