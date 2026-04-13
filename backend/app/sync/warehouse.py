"""仓库列表同步。"""

from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import get_logger
from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.models.warehouse import Warehouse
from app.saihu.endpoints.warehouse import list_warehouses
from app.sync.common import mark_sync_failed, mark_sync_running, mark_sync_success
from app.tasks.jobs import JobContext, register

logger = get_logger(__name__)
JOB_NAME = "sync_warehouse"
REPLENISH_SITE_RAW_MAX_LEN = 50


@register(JOB_NAME)
async def sync_warehouse_job(ctx: JobContext) -> None:
    await ctx.progress(current_step="同步仓库列表", total_steps=1)
    async with async_session_factory() as db:
        started = await mark_sync_running(db, JOB_NAME)

    count = 0
    try:
        async def _report_page(page_no: int, total_page: int, rows_count: int) -> None:
            if total_page <= 0:
                return
            await ctx.progress(
                total_steps=total_page,
                step_detail=f"第 {page_no} / {total_page} 页，当前页 {rows_count} 条，已处理 {count} 条",
            )

        async with async_session_factory() as db:
            async for raw in list_warehouses(on_page=_report_page):
                await _upsert_warehouse(db, raw)
                count += 1
            await db.commit()

        async with async_session_factory() as db:
            await mark_sync_success(db, JOB_NAME, started)
        logger.info("sync_warehouse_done", count=count)
        await ctx.progress(current_step="完成", step_detail=f"共 {count} 个仓库")
    except Exception as exc:
        async with async_session_factory() as db:
            await mark_sync_failed(db, JOB_NAME, str(exc))
        raise


async def _upsert_warehouse(db, raw: dict[str, Any]) -> None:
    warehouse_id = str(raw.get("id") or "")
    if not warehouse_id:
        return
    type_raw = raw.get("type")
    type_int = int(type_raw) if type_raw is not None and str(type_raw).lstrip("-").isdigit() else 0

    values = {
        "id": warehouse_id,
        "name": raw.get("name") or warehouse_id,
        "type": type_int,
        "replenish_site_raw": _normalize_replenish_site(raw.get("replenishSite")),
        "last_sync_at": now_beijing(),
    }

    stmt = pg_insert(Warehouse).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "name": values["name"],
            "type": values["type"],
            "replenish_site_raw": values["replenish_site_raw"],
            "last_sync_at": values["last_sync_at"],
        },
    )
    await db.execute(stmt)


def _normalize_replenish_site(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) <= REPLENISH_SITE_RAW_MAX_LEN:
        return text
    return text[: REPLENISH_SITE_RAW_MAX_LEN - 1] + "…"
