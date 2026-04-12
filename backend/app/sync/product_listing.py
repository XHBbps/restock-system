"""Sync online product listings from Saihu."""

from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.timezone import marketplace_to_country, now_beijing
from app.db.session import async_session_factory
from app.models.product_listing import ProductListing
from app.saihu.endpoints.product_listing import list_product_listings
from app.sync.common import mark_sync_failed, mark_sync_running, mark_sync_success
from app.tasks.jobs import JobContext, register

logger = get_logger(__name__)
JOB_NAME = "sync_product_listing"


@register(JOB_NAME)
async def sync_product_listing_job(ctx: JobContext) -> None:
    await ctx.progress(current_step="开始同步在线产品信息", total_steps=1)
    async with async_session_factory() as db:
        started = await mark_sync_running(db, JOB_NAME)

    inserted = 0
    try:
        async with async_session_factory() as db:
            async for raw in list_product_listings(only_matched=True, only_active=True):
                await _upsert_listing(db, raw)
                inserted += 1
                if inserted % 50 == 0:
                    await db.commit()
                    await ctx.progress(step_detail=f"已处理 {inserted} 条")
            await db.commit()

        async with async_session_factory() as db:
            await mark_sync_success(db, JOB_NAME, started)
        logger.info("sync_product_listing_done", count=inserted)
        await ctx.progress(current_step="完成", step_detail=f"共 {inserted} 条 listing")
    except Exception as exc:
        async with async_session_factory() as db:
            await mark_sync_failed(db, JOB_NAME, str(exc))
        raise


def _normalize_online_status(status: Any) -> str:
    value = str(status or "").strip()
    if not value:
        return "active"
    return value.lower()


async def _upsert_listing(db: AsyncSession, raw: dict[str, Any]) -> None:
    commodity_sku = raw.get("commoditySku")
    commodity_id = raw.get("commodityId")
    if not commodity_sku or not commodity_id:
        return

    marketplace_id = raw.get("marketplaceId") or ""
    mkt_normalized = marketplace_to_country(marketplace_id) or marketplace_id

    values = {
        "commodity_sku": commodity_sku,
        "commodity_id": str(commodity_id),
        "shop_id": str(raw.get("shopId") or ""),
        "marketplace_id": mkt_normalized,
        "seller_sku": raw.get("sku"),
        "parent_sku": raw.get("parentSku"),
        "commodity_name": raw.get("title") or raw.get("commodityName"),
        "main_image": raw.get("mainImage"),
        "day7_sale_num": _to_int(raw.get("day7SaleNum")),
        "day14_sale_num": _to_int(raw.get("day14SaleNum")),
        "day30_sale_num": _to_int(raw.get("day30SaleNum")),
        "is_matched": True,
        "online_status": _normalize_online_status(raw.get("onlineStatus")),
        "last_sync_at": now_beijing(),
    }

    stmt = pg_insert(ProductListing).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["shop_id", "marketplace_id", "seller_sku"],
        set_={
            k: v for k, v in values.items() if k not in ("shop_id", "marketplace_id", "seller_sku")
        },
    )
    await db.execute(stmt)


def _to_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
