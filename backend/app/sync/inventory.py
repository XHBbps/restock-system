"""库存明细同步。
仅写入 `inventory_snapshot_latest` 的 `available + reserved`。
`stockWait` 由 `sync_out_records` 独立维护。
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.country_mapping import apply_eu_mapping, load_eu_countries
from app.core.logging import get_logger
from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.models.inventory import InventorySnapshotLatest
from app.models.warehouse import Warehouse
from app.saihu.endpoints.inventory import list_inventory_items
from app.sync.common import mark_sync_failed, mark_sync_running, mark_sync_success
from app.tasks.jobs import JobContext, register

logger = get_logger(__name__)
JOB_NAME = "sync_inventory"


@register(JOB_NAME)
async def sync_inventory_job(ctx: JobContext) -> None:
    await ctx.progress(current_step="同步库存明细", total_steps=1)
    async with async_session_factory() as db:
        started = await mark_sync_running(db, JOB_NAME)

    count = 0
    try:
        async with async_session_factory() as db:
            warehouse_country_map = await _load_warehouse_countries(db)
            eu_countries = await load_eu_countries(db)

            async def _report_page(page_no: int, total_page: int, rows_count: int) -> None:
                if total_page <= 0:
                    return
                await ctx.progress(
                    total_steps=total_page,
                    step_detail=f"第 {page_no} / {total_page} 页，当前页 {rows_count} 条，已处理 {count} 条",
                )

            batch_size = 500
            async for raw in list_inventory_items(on_page=_report_page):
                await _upsert_inventory(db, raw, warehouse_country_map, eu_countries)
                count += 1
                if count % batch_size == 0:
                    await db.commit()
            await db.commit()  # 提交最后不足一批的剩余记录

        async with async_session_factory() as db:
            await mark_sync_success(db, JOB_NAME, started)
        logger.info("sync_inventory_done", count=count)
        await ctx.progress(current_step="完成", step_detail=f"共 {count} 行库存")
    except Exception as exc:
        async with async_session_factory() as db:
            await mark_sync_failed(db, JOB_NAME, str(exc))
        raise


async def _load_warehouse_countries(db: AsyncSession) -> dict[str, str | None]:
    rows = (await db.execute(select(Warehouse.id, Warehouse.country))).all()
    return dict(rows)


async def _upsert_inventory(
    db: AsyncSession,
    raw: dict[str, Any],
    warehouse_country_map: dict[str, str | None],
    eu_countries: set[str] | None = None,
) -> None:
    commodity_sku = raw.get("commoditySku")
    warehouse_id = str(raw.get("warehouseId") or "")
    if not commodity_sku or not warehouse_id:
        return
    if warehouse_id not in warehouse_country_map:
        return

    available = _to_int(raw.get("stockAvailable"), 0)
    reserved = _to_int(raw.get("stockOccupy"), 0)
    original_country = warehouse_country_map.get(warehouse_id)
    mapped_country = apply_eu_mapping(original_country, eu_countries or set())

    values = {
        "commodity_sku": commodity_sku,
        "warehouse_id": warehouse_id,
        "country": mapped_country,
        "original_country": original_country if mapped_country != original_country else None,
        "available": available,
        "reserved": reserved,
        "updated_at": now_beijing(),
    }

    stmt = pg_insert(InventorySnapshotLatest).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["commodity_sku", "warehouse_id"],
        set_={
            "country": values["country"],
            "original_country": values["original_country"],
            "available": values["available"],
            "reserved": values["reserved"],
            "updated_at": values["updated_at"],
        },
    )
    await db.execute(stmt)


def _to_int(v: Any, default: int = 0) -> int:
    if v is None or v == "":
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default
