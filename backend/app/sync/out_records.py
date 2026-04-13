"""Sync Saihu out-records into local tracking tables."""

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.timezone import parse_saihu_time
from app.db.session import async_session_factory
from app.models.in_transit import InTransitItem, InTransitRecord
from app.models.warehouse import Warehouse
from app.saihu.endpoints.out_records import list_in_transit_records
from app.sync.common import mark_sync_failed, mark_sync_running, mark_sync_success
from app.tasks.jobs import JobContext, register

logger = get_logger(__name__)
JOB_NAME = "sync_out_records"


@register(JOB_NAME)
async def sync_out_records_job(ctx: JobContext) -> None:
    await ctx.progress(current_step="同步在途出库单", total_steps=2)
    async with async_session_factory() as db:
        sync_start_time = await mark_sync_running(db, JOB_NAME)

    record_count = 0
    item_count = 0
    try:
        async with async_session_factory() as db:
            warehouse_country_map = await _load_warehouse_countries(db)
            async for raw in list_in_transit_records():
                ic = await _upsert_out_record(db, raw, warehouse_country_map, sync_start_time)
                record_count += 1
                item_count += ic
                if record_count % 50 == 0:
                    await db.commit()
                    await ctx.progress(step_detail=f"已处理 {record_count} 单 / {item_count} 行")
            await db.commit()

        # 老化处理:last_seen_at < sync_start_time 且 is_in_transit=true -> 标记 false
        await ctx.progress(current_step="老化标签消失的记录")
        aged = await _age_out_records(sync_start_time)

        async with async_session_factory() as db:
            await mark_sync_success(db, JOB_NAME, sync_start_time)
        logger.info(
            "sync_out_records_done",
            records=record_count,
            items=item_count,
            aged_out=aged,
        )
        await ctx.progress(
            current_step="完成",
            step_detail=f"在途单 {record_count} / 明细 {item_count} / 标签消失 {aged}",
        )
    except Exception as exc:
        async with async_session_factory() as db:
            await mark_sync_failed(db, JOB_NAME, str(exc))
        raise


async def _load_warehouse_countries(db: AsyncSession) -> dict[str, str | None]:
    rows = (await db.execute(select(Warehouse.id, Warehouse.country))).all()
    return dict(rows)


async def _upsert_out_record(
    db: AsyncSession,
    raw: dict[str, Any],
    warehouse_country_map: dict[str, str | None],
    sync_start_time,
) -> int:
    record_id = str(raw.get("id") or "")
    if not record_id:
        return 0

    target_warehouse_id = str(raw.get("targetFbaWarehouseId") or "") or None
    target_country = warehouse_country_map.get(target_warehouse_id) if target_warehouse_id else None

    rec_values = {
        "saihu_out_record_id": record_id,
        "warehouse_id": _to_optional_text(raw.get("warehouseId")),
        "out_warehouse_no": raw.get("outWarehouseNo"),
        "target_warehouse_id": target_warehouse_id
        if target_warehouse_id in warehouse_country_map
        else None,
        "target_country": target_country,
        "update_time": parse_saihu_time(raw.get("updateTime")),
        "type": _to_int(raw.get("type"), default=None),
        "type_name": _to_optional_text(raw.get("typeName")),
        "remark": raw.get("remark"),
        "status": str(raw.get("status") or "") or None,
        "is_in_transit": True,
        "last_seen_at": sync_start_time,
    }
    stmt = pg_insert(InTransitRecord).values(**rec_values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["saihu_out_record_id"],
        set_={
            "warehouse_id": rec_values["warehouse_id"],
            "out_warehouse_no": rec_values["out_warehouse_no"],
            "target_warehouse_id": rec_values["target_warehouse_id"],
            "target_country": rec_values["target_country"],
            "update_time": rec_values["update_time"],
            "type": rec_values["type"],
            "type_name": rec_values["type_name"],
            "remark": rec_values["remark"],
            "status": rec_values["status"],
            "is_in_transit": True,
            "last_seen_at": sync_start_time,
        },
    )
    await db.execute(stmt)

    # P1-3 审查结论: InTransitItem 无自然唯一约束(同 record 可含重复 SKU),
    # 保留 delete+insert 模式。delete 和 insert 在同一个 db session 内,
    # 只有 batch commit(每 50 条)时才提交,所以单条记录的 delete+insert 是原子的。
    await db.execute(delete(InTransitItem).where(InTransitItem.saihu_out_record_id == record_id))

    items: list[dict[str, Any]] = []
    for raw_item in raw.get("items") or []:
        commodity_sku = raw_item.get("commoditySku")
        if not commodity_sku:
            continue
        goods = _to_int(raw_item.get("goods"), 0)
        if goods <= 0:
            continue
        items.append(
            {
                "saihu_out_record_id": record_id,
                "commodity_id": _to_optional_text(raw_item.get("commodityId")),
                "commodity_sku": commodity_sku,
                "goods": goods,
                "per_purchase": _to_decimal(raw_item.get("perPurchase")),
            }
        )
    if items:
        await db.execute(pg_insert(InTransitItem).values(items))
    return len(items)


async def _age_out_records(sync_start_time) -> int:
    """将本次未见到的活跃记录标记为非在途。"""
    async with async_session_factory() as db:
        result = await db.execute(
            text(
                """
                UPDATE in_transit_record
                SET is_in_transit = false,
                    updated_at = now()
                WHERE is_in_transit = true
                  AND last_seen_at < :sync_start
                RETURNING saihu_out_record_id
                """
            ),
            {"sync_start": sync_start_time},
        )
        ids = [row[0] for row in result.all()]
        await db.commit()
        return len(ids)


def _to_int(v: Any, default: int | None = 0) -> int | None:
    if v is None or v == "":
        return default
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _to_optional_text(v: Any) -> str | None:
    value = str(v or "").strip()
    return value or None


def _to_decimal(v: Any) -> Decimal | None:
    value = _to_optional_text(v)
    if value is None:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None
