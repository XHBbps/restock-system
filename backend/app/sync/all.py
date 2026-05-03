"""Composite full-sync job."""

from app.sync.inventory import sync_inventory_job
from app.sync.order_list import sync_order_list_job
from app.sync.out_records import sync_out_records_job
from app.sync.product_listing import sync_product_listing_job
from app.sync.shop import sync_shop_job
from app.sync.warehouse import sync_warehouse_job
from app.tasks.jobs import JobContext, JobHandler, register

SYNC_ALL_STEPS: list[tuple[str, JobHandler]] = [
    ("店铺列表", sync_shop_job),
    ("仓库列表", sync_warehouse_job),
    ("在线产品", sync_product_listing_job),
    ("库存明细", sync_inventory_job),
    ("出库记录", sync_out_records_job),
    ("订单处理列表", sync_order_list_job),
]


@register("sync_all")
async def sync_all_job(ctx: JobContext) -> None:
    total = len(SYNC_ALL_STEPS)
    await ctx.progress(
        current_step="全量同步",
        step_detail=f"开始执行 {total} 个同步任务",
        total_steps=total,
    )

    for index, (label, handler) in enumerate(SYNC_ALL_STEPS, start=1):
        await ctx.progress(
            current_step=f"{index}/{total}",
            step_detail=f"执行 {label}",
            total_steps=total,
        )
        await handler(ctx)

    await ctx.progress(
        current_step="完成",
        step_detail=f"已串行完成 {total} 个同步任务",
        total_steps=total,
    )
