"""订单列表同步。"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.timezone import marketplace_to_country, now_beijing, parse_saihu_time
from app.db.session import async_session_factory
from app.models.order import OrderHeader, OrderItem
from app.models.shop import Shop
from app.models.sync_state import SyncState
from app.saihu.endpoints.order_list import list_orders
from app.sync.common import mark_sync_failed, mark_sync_running, mark_sync_success
from app.tasks.jobs import JobContext, register

logger = get_logger(__name__)
JOB_NAME = "sync_order_list"

INITIAL_BACKFILL_DAYS = 30
DEFAULT_OVERLAP_MINUTES = 5


@register(JOB_NAME)
async def sync_order_list_job(ctx: JobContext) -> None:
    await ctx.progress(current_step="同步订单列表", total_steps=1)
    async with async_session_factory() as db:
        started = await mark_sync_running(db, JOB_NAME)
        date_start, date_end = await _compute_window(db, started)
        shop_ids = await _resolve_shop_ids(db)

    logger.info("sync_order_list_window", start=date_start, end=date_end, shops=len(shop_ids or []))
    if shop_ids == []:
        async with async_session_factory() as db:
            await mark_sync_success(db, JOB_NAME, started)
        logger.info("sync_order_list_skipped_no_enabled_shops", start=date_start, end=date_end)
        await ctx.progress(current_step="完成", step_detail="未启用任何店铺，跳过同步 0 / 0")
        return

    order_count = 0
    item_count = 0
    BATCH_SIZE = 500
    try:
        async def _report_page(page_no: int, total_page: int, rows_count: int) -> None:
            if total_page <= 0:
                return
            await ctx.progress(
                total_steps=total_page,
                step_detail=(
                    f"第 {page_no} / {total_page} 页，当前页 {rows_count} 单，"
                    f"已处理 {order_count} 单 / {item_count} 行"
                ),
            )

        async with async_session_factory() as db:
            async for raw in list_orders(
                date_start=date_start.strftime("%Y-%m-%d %H:%M:%S"),
                date_end=date_end.strftime("%Y-%m-%d %H:%M:%S"),
                date_type="updateDateTime",
                shop_ids=shop_ids,
                on_page=_report_page,
            ):
                ic = await _upsert_order(db, raw)
                order_count += 1
                item_count += ic
                if order_count % BATCH_SIZE == 0:
                    await db.commit()
            await db.commit()

        async with async_session_factory() as db:
            await mark_sync_success(db, JOB_NAME, started)
        logger.info("sync_order_list_done", orders=order_count, items=item_count)
        await ctx.progress(current_step="完成", step_detail=f"订单 {order_count} / 明细 {item_count}")
    except Exception as exc:
        async with async_session_factory() as db:
            await mark_sync_failed(db, JOB_NAME, str(exc))
        raise


async def _compute_window(
    db: AsyncSession, now: datetime, overlap_minutes: int = DEFAULT_OVERLAP_MINUTES,
) -> tuple[datetime, datetime]:
    state = (
        await db.execute(select(SyncState).where(SyncState.job_name == JOB_NAME))
    ).scalar_one_or_none()
    if state and state.last_success_at:
        date_start = state.last_success_at - timedelta(minutes=overlap_minutes)
    else:
        date_start = now - timedelta(days=INITIAL_BACKFILL_DAYS)
    return date_start, now


async def _resolve_shop_ids(db: AsyncSession) -> list[str] | None:
    """根据全局参数 shop_sync_mode 决定是否过滤 shop_ids。"""
    from app.models.global_config import GlobalConfig

    config = (
        await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
    ).scalar_one_or_none()
    if config is None or config.shop_sync_mode == "all":
        return None
    rows = (
        (
            await db.execute(
                select(Shop.id).where(Shop.sync_enabled.is_(True)).where(Shop.status == "0")
            )
        )
        .scalars()
        .all()
    )
    return list(rows) if rows else []


async def _upsert_order(db: AsyncSession, raw: dict[str, Any]) -> int:
    shop_id = str(raw.get("shopId") or "")
    amazon_order_id = raw.get("amazonOrderId")
    if not shop_id or not amazon_order_id:
        return 0

    marketplace_id_raw = raw.get("marketplaceId") or ""
    country_code = marketplace_to_country(marketplace_id_raw) or ""
    marketplace_id = country_code or marketplace_id_raw

    purchase_date = parse_saihu_time(raw.get("purchaseDate"), marketplace_id_raw) or now_beijing()
    last_update_date = (
        parse_saihu_time(raw.get("lastUpdateDate"), marketplace_id_raw) or purchase_date
    )

    header_values = {
        "shop_id": shop_id,
        "amazon_order_id": amazon_order_id,
        "marketplace_id": marketplace_id,
        "country_code": country_code or "ZZ",
        "order_status": raw.get("orderStatus") or "Unknown",
        "order_total_currency": raw.get("orderTotalCurrency"),
        "order_total_amount": _to_decimal(raw.get("orderTotalAmount")),
        "fulfillment_channel": raw.get("fulfillmentChannel"),
        "purchase_date": purchase_date,
        "last_update_date": last_update_date,
        "is_buyer_requested_cancel": str(raw.get("isBuyerRequestedCancel") or "0") == "1",
        "refund_status": str(raw.get("refundStatus") or "") or None,
        "last_sync_at": now_beijing(),
    }
    header_stmt = pg_insert(OrderHeader).values(**header_values).returning(OrderHeader.id)
    update_set = {k: v for k, v in header_values.items() if k not in ("shop_id", "amazon_order_id")}
    header_stmt = header_stmt.on_conflict_do_update(
        constraint="uq_order_header_key",
        set_=update_set,
    )
    order_id = (await db.execute(header_stmt)).scalar_one()

    items_to_insert: list[dict[str, Any]] = []
    seen_item_ids: list[str] = []
    for raw_item in raw.get("orderItemVoList") or []:
        order_item_id = raw_item.get("orderItemId")
        commodity_sku = raw_item.get("commoditySku")
        if not order_item_id or not commodity_sku:
            continue
        oid = str(order_item_id)
        seen_item_ids.append(oid)
        items_to_insert.append(
            {
                "order_id": order_id,
                "order_item_id": oid,
                "commodity_sku": commodity_sku,
                "seller_sku": raw_item.get("sellerSku"),
                "quantity_ordered": _to_int(raw_item.get("quantityOrdered")),
                "quantity_shipped": _to_int(raw_item.get("quantityShipped")),
                "quantity_unfulfillable": _to_int(raw_item.get("quantityUnfulfillable")),
                "refund_num": _to_int(raw_item.get("refundNum")),
                "item_price_currency": raw_item.get("itemPriceCurrency"),
                "item_price_amount": _to_decimal(raw_item.get("itemPriceAmount")),
            }
        )
    if items_to_insert:
        item_stmt = pg_insert(OrderItem).values(items_to_insert)
        item_stmt = item_stmt.on_conflict_do_update(
            index_elements=["order_id", "order_item_id"],
            set_={
                "commodity_sku": item_stmt.excluded.commodity_sku,
                "seller_sku": item_stmt.excluded.seller_sku,
                "quantity_ordered": item_stmt.excluded.quantity_ordered,
                "quantity_shipped": item_stmt.excluded.quantity_shipped,
                "quantity_unfulfillable": item_stmt.excluded.quantity_unfulfillable,
                "refund_num": item_stmt.excluded.refund_num,
                "item_price_currency": item_stmt.excluded.item_price_currency,
                "item_price_amount": item_stmt.excluded.item_price_amount,
            },
        )
        await db.execute(item_stmt)
    if seen_item_ids:
        await db.execute(
            delete(OrderItem).where(
                OrderItem.order_id == order_id,
                OrderItem.order_item_id.not_in(seen_item_ids),
            )
        )
    elif not items_to_insert:
        await db.execute(delete(OrderItem).where(OrderItem.order_id == order_id))
    return len(items_to_insert)


def _to_int(v: Any, default: int = 0) -> int:
    if v is None or v == "":
        return default
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _to_decimal(v: Any) -> Any:
    if v is None or v == "":
        return None
    from decimal import Decimal, InvalidOperation

    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None
