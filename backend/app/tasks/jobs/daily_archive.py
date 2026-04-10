"""每日 02:00 库存归档任务。

将 inventory_snapshot_latest 整表追加到 inventory_snapshot_history,
带上 snapshot_date = today。
"""

from sqlalchemy import text

from app.core.logging import get_logger
from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.tasks.jobs import JobContext, register

logger = get_logger(__name__)


@register("daily_archive")
async def daily_archive_job(ctx: JobContext) -> None:
    await ctx.progress(current_step="开始归档库存快照", total_steps=1)

    today = now_beijing().date()
    async with async_session_factory() as db:
        result = await db.execute(
            text(
                """
                INSERT INTO inventory_snapshot_history
                  (commodity_sku, warehouse_id, country, available, reserved, snapshot_date)
                SELECT
                  commodity_sku, warehouse_id, country, available, reserved, :snapshot_date
                FROM inventory_snapshot_latest
                ON CONFLICT (commodity_sku, warehouse_id, snapshot_date) DO NOTHING
                """
            ),
            {"snapshot_date": today},
        )
        row_count = result.rowcount or 0
        await db.commit()

    logger.info("daily_archive_done", rows=row_count, date=str(today))
    await ctx.progress(
        current_step="完成", step_detail=f"归档 {row_count} 行 -> {today}"
    )
