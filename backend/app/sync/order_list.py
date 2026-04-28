"""订单列表同步。"""

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.countries import normalize_observed_country_code, normalize_source_country_or_unknown
from app.core.country_mapping import apply_eu_mapping, load_eu_countries
from app.core.logging import get_logger
from app.core.timezone import marketplace_to_country, now_beijing, parse_saihu_time
from app.db.session import async_session_factory
from app.models.order import (
    ORDER_SOURCE_AMAZON,
    ORDER_SOURCE_MULTIPLATFORM,
    OrderHeader,
    OrderItem,
)
from app.models.shop import Shop
from app.models.sync_state import SyncState
from app.saihu.endpoints.multiplatform_order import list_multiplatform_orders
from app.saihu.endpoints.order_list import list_orders
from app.sync.common import mark_sync_failed, mark_sync_running, mark_sync_success
from app.tasks.jobs import JobContext, register

logger = get_logger(__name__)
JOB_NAME = "sync_order_list"

INITIAL_BACKFILL_DAYS = 30
MULTIPLATFORM_ROLLING_DAYS = 30
DEFAULT_OVERLAP_MINUTES = 5
MULTIPLATFORM_STATUS_MAP: dict[str, str] = {
    "Unknown": "Unknown",
    "Pending": "Pending",
    "Unshipped": "Unshipped",
    "PartiallyShipped": "PartiallyShipped",
    "Shipped": "Shipped",
    "PartiallyCompleted": "PartiallyShipped",
    "Completed": "Shipped",
    "Canceled": "Canceled",
    "Refunded": "Canceled",
    "已完成": "Shipped",
    "已发货": "Shipped",
    "部分发货": "PartiallyShipped",
    "待发货": "Unshipped",
    "未付款": "Pending",
    "已取消": "Canceled",
}
SHIPMENT_STATUSES = {"Shipped", "PartiallyShipped"}


@register(JOB_NAME)
async def sync_order_list_job(ctx: JobContext) -> None:
    await ctx.progress(current_step="同步订单列表", total_steps=1)
    async with async_session_factory() as db:
        started = await mark_sync_running(db, JOB_NAME)
        date_start, date_end = await _compute_window(db, started)
        multi_date_start = started - timedelta(days=MULTIPLATFORM_ROLLING_DAYS)
        shop_ids = await _resolve_shop_ids(db)
        eu_countries = await load_eu_countries(db)

    logger.info("sync_order_list_window", start=date_start, end=date_end, shops=len(shop_ids or []))
    if shop_ids == []:
        async with async_session_factory() as db:
            await mark_sync_success(db, JOB_NAME, started)
        logger.info("sync_order_list_skipped_no_enabled_shops", start=date_start, end=date_end)
        await ctx.progress(current_step="完成", step_detail="未启用任何店铺，跳过同步 0 / 0")
        return

    order_count = 0
    item_count = 0
    batch_size = 500
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
                ic = await _upsert_order(db, raw, eu_countries)
                order_count += 1
                item_count += ic
                if order_count % batch_size == 0:
                    await db.commit()
            async for raw in list_multiplatform_orders(
                date_start=multi_date_start.strftime("%Y-%m-%d"),
                date_end=date_end.strftime("%Y-%m-%d"),
                date_type="purchase",
                shop_ids=shop_ids,
                on_page=_report_page,
            ):
                ic = await _upsert_multiplatform_order(db, raw, eu_countries)
                order_count += 1
                item_count += ic
                if order_count % batch_size == 0:
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


async def _upsert_order(
    db: AsyncSession,
    raw: dict[str, Any],
    eu_countries: set[str] | None = None,
) -> int:
    shop_id = str(raw.get("shopId") or "")
    amazon_order_id = str(raw.get("amazonOrderId") or "")
    if not shop_id or not amazon_order_id:
        return 0

    marketplace_id_raw = raw.get("marketplaceId") or ""
    original_country_code = marketplace_to_country(marketplace_id_raw)
    if original_country_code is None:
        original_country_code = normalize_observed_country_code(marketplace_id_raw) or ""
    mapped_country = apply_eu_mapping(original_country_code, eu_countries or set()) or ""
    country_code = mapped_country or "ZZ"
    if country_code == "ZZ":
        logger.warning(
            "order_country_unrecognized",
            source=ORDER_SOURCE_AMAZON,
            shop_id=shop_id,
            order_no=amazon_order_id,
            marketplace_id=marketplace_id_raw,
            fallback_country="ZZ",
        )
    marketplace_id = country_code

    purchase_date = parse_saihu_time(raw.get("purchaseDate"), marketplace_id_raw) or now_beijing()
    last_update_date = (
        parse_saihu_time(raw.get("lastUpdateDate"), marketplace_id_raw) or purchase_date
    )

    header_values = {
        "shop_id": shop_id,
        "amazon_order_id": amazon_order_id,
        "source": ORDER_SOURCE_AMAZON,
        "order_platform": ORDER_SOURCE_AMAZON,
        "marketplace_id": marketplace_id,
        "country_code": country_code,
        "original_country_code": original_country_code if mapped_country != original_country_code else None,
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
    update_set = {
        k: v
        for k, v in header_values.items()
        if k not in ("shop_id", "amazon_order_id", "source")
    }
    header_stmt = header_stmt.on_conflict_do_update(  # type: ignore[attr-defined]
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


async def _upsert_multiplatform_order(
    db: AsyncSession,
    raw: dict[str, Any],
    eu_countries: set[str] | None = None,
) -> int:
    shop_id = str(raw.get("shopId") or "")
    order_no = str(raw.get("orderNo") or "")
    if not shop_id or not order_no:
        return 0

    platform_name = str(raw.get("platformName") or "").strip() or ORDER_SOURCE_MULTIPLATFORM
    original_country_code = _multiplatform_country(
        raw,
        shop_id=shop_id,
        order_no=order_no,
        platform_name=platform_name,
    )
    mapped_country = apply_eu_mapping(original_country_code, eu_countries or set()) or ""
    country_code = mapped_country or original_country_code
    marketplace_id = country_code

    purchase_date = parse_saihu_time(raw.get("purchaseDate"), country_code) or now_beijing()
    last_update_date = parse_saihu_time(raw.get("payTime"), country_code) or purchase_date
    order_status = _normalize_multiplatform_status(raw.get("orderStatus"))
    order_currency = raw.get("currency")

    header_values = {
        "shop_id": shop_id,
        "amazon_order_id": order_no,
        "source": ORDER_SOURCE_MULTIPLATFORM,
        "order_platform": platform_name,
        "marketplace_id": marketplace_id,
        "country_code": country_code,
        "original_country_code": original_country_code if mapped_country != original_country_code else None,
        "order_status": order_status,
        "order_total_currency": order_currency,
        "order_total_amount": _to_decimal(raw.get("totalAmount")),
        "fulfillment_channel": None,
        "purchase_date": purchase_date,
        "last_update_date": last_update_date,
        "is_buyer_requested_cancel": order_status == "Canceled",
        "refund_status": None,
        "last_sync_at": now_beijing(),
    }
    header_stmt = pg_insert(OrderHeader).values(**header_values).returning(OrderHeader.id)
    update_set = {
        k: v
        for k, v in header_values.items()
        if k not in ("shop_id", "amazon_order_id", "source")
    }
    header_stmt = header_stmt.on_conflict_do_update(  # type: ignore[attr-defined]
        constraint="uq_order_header_key",
        set_=update_set,
    )
    order_id = (await db.execute(header_stmt)).scalar_one()

    items_to_insert: list[dict[str, Any]] = []
    seen_item_ids: list[str] = []
    for index, raw_item in enumerate(_multiplatform_items(raw), start=1):
        order_item_id = raw_item.get("orderItemId")
        commodity_sku = raw_item.get("localSku")
        if not commodity_sku:
            logger.warning(
                "multiplatform_order_item_skipped_missing_local_sku",
                shop_id=shop_id,
                order_no=order_no,
                platform_name=platform_name,
                order_item_id=order_item_id,
            )
            continue
        oid = str(order_item_id or f"line-{index}")
        sale_num = _to_int(raw_item.get("saleNum"))
        seen_item_ids.append(oid)
        items_to_insert.append(
            {
                "order_id": order_id,
                "order_item_id": oid,
                "commodity_sku": str(commodity_sku),
                "seller_sku": raw_item.get("msku"),
                "quantity_ordered": sale_num,
                "quantity_shipped": sale_num if order_status in SHIPMENT_STATUSES else 0,
                "quantity_unfulfillable": 0,
                "refund_num": 0,
                "item_price_currency": raw_item.get("currency") or order_currency,
                "item_price_amount": _to_decimal(raw_item.get("originalPrice")),
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
    else:
        await db.execute(delete(OrderItem).where(OrderItem.order_id == order_id))
    return len(items_to_insert)


def _normalize_multiplatform_status(raw_status: Any) -> str:
    status = str(raw_status or "").strip()
    return MULTIPLATFORM_STATUS_MAP.get(status, "Unknown")


def _multiplatform_country(
    raw: dict[str, Any],
    *,
    shop_id: str,
    order_no: str,
    platform_name: str,
) -> str:
    country_raw = raw.get("marketplaceCode")
    country = normalize_observed_country_code(country_raw)
    if country is None:
        extra_info = raw.get("extraInfo")
        if isinstance(extra_info, str):
            try:
                parsed_extra_info = json.loads(extra_info)
            except json.JSONDecodeError:
                parsed_extra_info = None
            extra_info = parsed_extra_info
        if isinstance(extra_info, dict):
            country_raw = extra_info.get("warehouse_country")
            country = normalize_observed_country_code(country_raw)
    if country is not None:
        return country
    return normalize_source_country_or_unknown(
        country_raw,
        event="multiplatform_order_country_unrecognized",
        shop_id=shop_id,
        order_no=order_no,
        platform_name=platform_name,
    )


def _multiplatform_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    for key in (
        "skuInfoVo",
        "orderItemVoList",
        "orderItemList",
        "itemList",
        "items",
        "detailList",
        "orderDetails",
    ):
        value = raw.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


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
