"""店铺列表同步（手动触发）。

调用 /api/shop/pageList.json，UPSERT 到本地 shop 表。
保留所有 status 的店铺供 UI 显示，由前端按 status='0' 过滤可勾选项。
"""

from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import get_logger
from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.models.shop import Shop
from app.saihu.endpoints.shop import list_shops
from app.sync.common import mark_sync_failed, mark_sync_running, mark_sync_success
from app.tasks.jobs import JobContext, register

logger = get_logger(__name__)
JOB_NAME = "sync_shop"


@register(JOB_NAME)
async def sync_shop_job(ctx: JobContext) -> None:
    await ctx.progress(current_step="同步店铺列表", total_steps=1)
    async with async_session_factory() as db:
        started = await mark_sync_running(db, JOB_NAME)

    count = 0
    try:
        async with async_session_factory() as db:
            async for raw in list_shops():
                await _upsert_shop(db, raw)
                count += 1
            await db.commit()
        async with async_session_factory() as db:
            await mark_sync_success(db, JOB_NAME, started)
        logger.info("sync_shop_done", count=count)
        await ctx.progress(current_step="完成", step_detail=f"共 {count} 个店铺")
    except Exception as exc:
        async with async_session_factory() as db:
            await mark_sync_failed(db, JOB_NAME, str(exc))
        raise


async def _upsert_shop(db, raw: dict[str, Any]) -> None:
    shop_id = str(raw.get("id") or "")
    if not shop_id:
        return
    values = {
        "id": shop_id,
        "name": raw.get("name") or shop_id,
        "seller_id": raw.get("sellerId"),
        "region": raw.get("region"),
        "marketplace_id": raw.get("marketplaceId"),
        "status": str(raw.get("status") or "0"),
        "ad_status": raw.get("adStatus"),
        "last_sync_at": now_beijing(),
    }
    stmt = pg_insert(Shop).values(**values)
    # 不覆盖 sync_enabled（用户手动维护）
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "name": values["name"],
            "seller_id": values["seller_id"],
            "region": values["region"],
            "marketplace_id": values["marketplace_id"],
            "status": values["status"],
            "ad_status": values["ad_status"],
            "last_sync_at": values["last_sync_at"],
        },
    )
    await db.execute(stmt)
