"""Sync Saihu out-records into local tracking tables."""

import re
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

REMARK_COUNTRY_MAP: dict[str, str] = {
    "阿联酋": "AE",
    "澳大利亚": "AU",
    "比利时": "BE",
    "巴西": "BR",
    "加拿大": "CA",
    "中国": "CN",
    "德国": "DE",
    "西班牙": "ES",
    "法国": "FR",
    "英国": "GB",
    "爱尔兰": "IE",
    "印度": "IN",
    "意大利": "IT",
    "日本": "JP",
    "墨西哥": "MX",
    "荷兰": "NL",
    "波兰": "PL",
    "沙特阿拉伯": "SA",
    "新加坡": "SG",
    "瑞典": "SE",
    "土耳其": "TR",
    "美国": "US",
}


@register(JOB_NAME)
async def sync_out_records_job(ctx: JobContext) -> None:
    await ctx.progress(current_step="同步在途出库单", total_steps=3)
    async with async_session_factory() as db:
        sync_start_time = await mark_sync_running(db, JOB_NAME)

    record_count = 0
    item_count = 0
    backfilled = 0
    backfill_skipped = 0
    total_steps = 3
    try:

        async def _report_page(page_no: int, total_page: int, rows_count: int) -> None:
            nonlocal total_steps
            if total_page <= 0:
                return
            total_steps = total_page + 2
            await ctx.progress(
                total_steps=total_steps,
                step_detail=(
                    f"第 {page_no} / {total_page} 页，当前页 {rows_count} 单，"
                    f"已处理 {record_count} 单 / {item_count} 行"
                ),
            )

        async with async_session_factory() as db:
            warehouse_ids = await _load_warehouse_ids(db)
            async for raw in list_in_transit_records(on_page=_report_page):
                item_count += await _upsert_out_record(db, raw, warehouse_ids, sync_start_time)
                record_count += 1
            await db.commit()

        await ctx.progress(
            current_step="回填目标国家",
            total_steps=total_steps,
            step_detail="根据备注回填历史空目标国家",
        )
        async with async_session_factory() as db:
            _, backfilled, backfill_skipped = await _backfill_target_country_from_remark(db)

        await ctx.progress(
            current_step="老化未见记录",
            total_steps=total_steps,
            step_detail="处理本次未再出现的在途记录",
        )
        aged = await _age_out_records(sync_start_time)

        async with async_session_factory() as db:
            await mark_sync_success(db, JOB_NAME, sync_start_time)
        logger.info(
            "sync_out_records_done",
            records=record_count,
            items=item_count,
            target_country_backfilled=backfilled,
            target_country_skipped=backfill_skipped,
            aged_out=aged,
        )
        await ctx.progress(
            current_step="完成",
            total_steps=total_steps,
            step_detail=(
                f"在途单 {record_count} / 明细 {item_count} / "
                f"回填国家 {backfilled} / 标记完结 {aged}"
            ),
        )
    except Exception as exc:
        async with async_session_factory() as db:
            await mark_sync_failed(db, JOB_NAME, str(exc))
        raise


async def _load_warehouse_ids(db: AsyncSession) -> set[str]:
    rows = (await db.execute(select(Warehouse.id))).scalars().all()
    return set(rows)


async def _upsert_out_record(
    db: AsyncSession,
    raw: dict[str, Any],
    warehouse_ids: set[str],
    sync_start_time,
) -> int:
    record_id = str(raw.get("id") or "")
    if not record_id:
        return 0

    target_warehouse_id = str(raw.get("targetFbaWarehouseId") or "") or None
    target_country = _extract_country_from_remark(raw.get("remark"))

    rec_values = {
        "saihu_out_record_id": record_id,
        "warehouse_id": _to_optional_text(raw.get("warehouseId")),
        "out_warehouse_no": raw.get("outWarehouseNo"),
        "target_warehouse_id": target_warehouse_id if target_warehouse_id in warehouse_ids else None,
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

    await db.execute(delete(InTransitItem).where(InTransitItem.saihu_out_record_id == record_id))

    items: list[dict[str, Any]] = []
    for raw_item in raw.get("items") or []:
        commodity_sku = raw_item.get("commoditySku")
        if not commodity_sku:
            continue
        goods = _to_int(raw_item.get("goods"), 0) or 0
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
    """Mark active rows not seen in this run as completed."""
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


async def _backfill_target_country_from_remark(db: AsyncSession) -> tuple[int, int, int]:
    rows = (
        await db.execute(
            select(InTransitRecord)
            .where(InTransitRecord.target_country.is_(None))
            .where(InTransitRecord.remark.is_not(None))
            .order_by(InTransitRecord.saihu_out_record_id.asc())
        )
    ).scalars().all()

    scanned = len(rows)
    updated = 0
    skipped = 0
    for record in rows:
        country = _extract_country_from_remark(record.remark)
        if country is None:
            skipped += 1
            continue
        record.target_country = country
        updated += 1

    await db.commit()
    return scanned, updated, skipped


def _extract_country_from_remark(raw_remark: Any) -> str | None:
    remark = _to_optional_text(raw_remark)
    if remark is None:
        return None

    normalized = re.sub(r"^\d{4}[-/.]?\d{2}[-/.]?\d{2}", "", remark).strip()
    tokens = [token.strip() for token in re.split(r"[-_/|,，、。\s]+", normalized) if token.strip()]
    for token in tokens:
        country = REMARK_COUNTRY_MAP.get(token)
        if country:
            return country

    for name, country in sorted(REMARK_COUNTRY_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if name in normalized:
            return country
    return None


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
