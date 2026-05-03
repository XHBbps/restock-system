"""Package shipment order list sync."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.countries import normalize_observed_country_code, normalize_source_country_or_unknown
from app.core.country_mapping import apply_eu_mapping, load_eu_countries
from app.core.logging import get_logger
from app.core.timezone import now_beijing, parse_saihu_time
from app.db.session import async_session_factory
from app.models.order import (
    ORDER_SOURCE_AMAZON,
    ORDER_SOURCE_MULTIPLATFORM,
    ORDER_SOURCE_PACKAGE,
    OrderDetail,
    OrderDetailFetchLog,
    OrderHeader,
    OrderItem,
)
from app.models.shop import Shop
from app.saihu.endpoints.package_ship import list_package_ship_orders
from app.sync.common import mark_sync_failed, mark_sync_running, mark_sync_success
from app.tasks.jobs import JobContext, register

logger = get_logger(__name__)
JOB_NAME = "sync_order_list"

ORDER_SYNC_ROLLING_MONTHS = 12
PACKAGE_PAGE_SIZE = 200
DEFAULT_BATCH_SIZE = 200
LEGACY_ORDER_SOURCES = (ORDER_SOURCE_AMAZON, ORDER_SOURCE_MULTIPLATFORM)
CANCELED_PACKAGE_STATUS = "has_canceled"


@register(JOB_NAME)
async def sync_order_list_job(ctx: JobContext) -> None:
    await ctx.progress(current_step="同步包裹订单列表", total_steps=1)
    async with async_session_factory() as db:
        started = await mark_sync_running(db, JOB_NAME)
        date_start, date_end = _compute_window(started)
        shop_ids = await _resolve_shop_ids(db)
        eu_countries = await load_eu_countries(db)

    logger.info(
        "sync_order_list_window",
        start=date_start,
        end=date_end,
        shops=len(shop_ids or []),
    )

    async with async_session_factory() as db:
        await _cleanup_legacy_orders(db)
        await db.commit()

    if shop_ids == []:
        async with async_session_factory() as db:
            await mark_sync_success(db, JOB_NAME, started, success_at=date_end)
        logger.info("sync_order_list_skipped_no_enabled_shops", start=date_start, end=date_end)
        await ctx.progress(
            current_step="完成", step_detail="未启用任何店铺，已清理旧订单并跳过同步 0 / 0"
        )
        return

    package_count = 0
    order_count = 0
    item_count = 0
    try:

        async def _report_page(page_no: int, total_page: int, rows_count: int) -> None:
            if total_page <= 0:
                return
            await ctx.progress(
                total_steps=total_page,
                step_detail=(
                    f"第 {page_no} / {total_page} 页，当前页 {rows_count} 个包裹，"
                    f"已处理 {order_count} 订单 / {item_count} 明细"
                ),
            )

        async with async_session_factory() as db:
            async for raw in list_package_ship_orders(
                purchase_date_start=date_start.strftime("%Y-%m-%d %H:%M:%S"),
                purchase_date_end=date_end.strftime("%Y-%m-%d %H:%M:%S"),
                shop_ids=shop_ids,
                page_size=PACKAGE_PAGE_SIZE,
                on_page=_report_page,
            ):
                orders_added, items_added = await _upsert_package_ship_order(db, raw, eu_countries)
                package_count += 1
                order_count += orders_added
                item_count += items_added
                if package_count % DEFAULT_BATCH_SIZE == 0:
                    await db.commit()
            await db.commit()

        async with async_session_factory() as db:
            await mark_sync_success(db, JOB_NAME, started, success_at=date_end)
        logger.info(
            "sync_order_list_done",
            packages=package_count,
            orders=order_count,
            items=item_count,
        )
        await ctx.progress(
            current_step="完成",
            step_detail=f"包裹 {package_count} / 订单 {order_count} / 明细 {item_count}",
        )
    except Exception as exc:
        async with async_session_factory() as db:
            await mark_sync_failed(db, JOB_NAME, str(exc))
        raise


def _compute_window(now: datetime) -> tuple[datetime, datetime]:
    return _subtract_calendar_months(now, ORDER_SYNC_ROLLING_MONTHS), now


def _subtract_calendar_months(value: datetime, months: int) -> datetime:
    month_index = value.year * 12 + value.month - 1 - months
    year = month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


async def _resolve_shop_ids(db: AsyncSession) -> list[str] | None:
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


async def _cleanup_legacy_orders(db: AsyncSession) -> None:
    await db.execute(
        delete(OrderDetailFetchLog).where(OrderDetailFetchLog.source.in_(LEGACY_ORDER_SOURCES))
    )
    await db.execute(delete(OrderDetail).where(OrderDetail.source.in_(LEGACY_ORDER_SOURCES)))
    await db.execute(delete(OrderHeader).where(OrderHeader.source.in_(LEGACY_ORDER_SOURCES)))


async def _upsert_package_ship_order(
    db: AsyncSession,
    raw: dict[str, Any],
    eu_countries: set[str] | None = None,
) -> tuple[int, int]:
    shop_id = str(raw.get("shopId") or "").strip()
    package_sn = str(
        raw.get("packageSn") or raw.get("packageNo") or raw.get("packageId") or ""
    ).strip()
    if not shop_id or not package_sn:
        logger.warning(
            "package_ship_order_skipped_missing_key",
            shop_id=shop_id or None,
            package_sn=package_sn or None,
        )
        return 0, 0

    platform_name = str(raw.get("platformName") or "").strip() or ORDER_SOURCE_PACKAGE
    shop_name = str(raw.get("shopName") or "").strip() or None
    package_status = str(raw.get("packageStatus") or raw.get("status") or "").strip() or "Unknown"
    raw_address = raw.get("address")
    address = cast(dict[str, Any], raw_address) if isinstance(raw_address, dict) else {}
    postal_code = _clean_text(address.get("postalCode") if isinstance(address, dict) else None)
    country_code, original_country_code = _resolve_package_country(
        raw,
        shop_id=shop_id,
        package_sn=package_sn,
        platform_name=platform_name,
        eu_countries=eu_countries or set(),
    )
    marketplace_id = _clean_text(raw.get("marketplaceId")) or country_code

    orders = _extract_package_orders(raw)
    package_items = _extract_package_items(raw)
    order_map = _normalize_orders_from_package(raw, orders, package_items)
    if not order_map:
        logger.warning(
            "package_ship_order_missing_amazon_order_id",
            shop_id=shop_id,
            package_sn=package_sn,
        )
        return 0, 0

    items_by_order = _group_items_by_order(package_items, order_map)

    orders_inserted = 0
    items_inserted = 0
    for amazon_order_id, order_meta in order_map.items():
        purchase_date = _parse_order_date(
            order_meta.get("purchaseDate") or raw.get("purchaseDate"),
            raw.get("purchaseDate"),
            marketplace_id,
        )
        last_update_date = _parse_order_date(
            order_meta.get("lastUpdateDate") or raw.get("updateTime") or raw.get("lastUpdateDate"),
            raw.get("updateTime") or raw.get("lastUpdateDate") or order_meta.get("purchaseDate"),
            marketplace_id,
        )
        header_values = {
            "shop_id": shop_id,
            "amazon_order_id": amazon_order_id,
            "source": ORDER_SOURCE_PACKAGE,
            "order_platform": platform_name,
            "package_sn": package_sn,
            "package_status": package_status,
            "shop_name": shop_name,
            "postal_code": postal_code,
            "marketplace_id": marketplace_id,
            "country_code": country_code,
            "original_country_code": (
                original_country_code
                if original_country_code and original_country_code != country_code
                else None
            ),
            "order_status": package_status,
            "order_total_currency": _clean_text(
                order_meta.get("orderTotalCurrency") or raw.get("orderTotalCurrency")
            ),
            "order_total_amount": _to_decimal(
                order_meta.get("orderTotalAmount") or raw.get("orderTotalAmount")
            ),
            "fulfillment_channel": _clean_text(
                order_meta.get("fulfillmentChannel") or raw.get("fulfillmentChannel")
            ),
            "purchase_date": purchase_date,
            "last_update_date": last_update_date,
            "is_buyer_requested_cancel": package_status == CANCELED_PACKAGE_STATUS,
            "refund_status": None,
            "last_sync_at": now_beijing(),
        }
        header_stmt = pg_insert(OrderHeader).values(**header_values).returning(OrderHeader.id)
        update_set = {
            k: v
            for k, v in header_values.items()
            if k not in ("shop_id", "amazon_order_id", "source", "package_sn")
        }
        header_stmt = header_stmt.on_conflict_do_update(  # type: ignore[attr-defined]
            constraint="uq_order_header_key",
            set_=update_set,
        )
        order_id = (await db.execute(header_stmt)).scalar_one()
        orders_inserted += 1

        order_items = items_by_order.get(amazon_order_id, [])
        seen_item_ids: list[str] = []
        item_values: list[dict[str, Any]] = []
        for index, raw_item in enumerate(order_items, start=1):
            commodity_sku = _clean_text(raw_item.get("commoditySku"))
            if not commodity_sku:
                logger.warning(
                    "package_ship_item_skipped_missing_commodity_sku",
                    shop_id=shop_id,
                    package_sn=package_sn,
                    amazon_order_id=amazon_order_id,
                    item_index=index,
                )
                continue
            order_item_id = (
                _clean_text(raw_item.get("orderItemId"))
                or f"{package_sn}:{amazon_order_id}:{index}"
            )
            seen_item_ids.append(order_item_id)
            quantity = _to_int(
                raw_item.get("quantityOrdered")
                or raw_item.get("saleNum")
                or raw_item.get("quantity")
                or raw_item.get("qty")
            )
            item_values.append(
                {
                    "order_id": order_id,
                    "order_item_id": order_item_id,
                    "commodity_sku": commodity_sku,
                    "seller_sku": _clean_text(raw_item.get("sellerSku")) or None,
                    "quantity_ordered": quantity,
                    "quantity_shipped": quantity,
                    "quantity_unfulfillable": 0,
                    "refund_num": 0,
                    "item_price_currency": _clean_text(
                        raw_item.get("itemPriceCurrency") or raw_item.get("currency")
                    ),
                    "item_price_amount": _to_decimal(
                        raw_item.get("itemPriceAmount") or raw_item.get("price")
                    ),
                }
            )
        if item_values:
            item_stmt = pg_insert(OrderItem).values(item_values)
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
            items_inserted += len(item_values)
        if seen_item_ids:
            await db.execute(
                delete(OrderItem).where(
                    OrderItem.order_id == order_id,
                    OrderItem.order_item_id.not_in(seen_item_ids),
                )
            )
        else:
            logger.warning(
                "package_ship_order_items_empty_preserve_existing",
                shop_id=shop_id,
                package_sn=package_sn,
                amazon_order_id=amazon_order_id,
                raw_item_count=len(order_items),
            )

    return orders_inserted, items_inserted


def _normalize_orders_from_package(
    raw: dict[str, Any],
    orders: list[dict[str, Any]],
    package_items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    order_map: dict[str, dict[str, Any]] = {}
    for order in orders:
        amazon_order_id = _clean_text(
            order.get("amazonOrderId") or order.get("orderNo") or order.get("orderId")
        )
        if not amazon_order_id:
            continue
        order_map[amazon_order_id] = order

    if not order_map:
        fallback_order_id = _clean_text(
            raw.get("amazonOrderId") or raw.get("orderNo") or raw.get("orderId")
        )
        if fallback_order_id:
            order_map[fallback_order_id] = {
                "amazonOrderId": fallback_order_id,
                "purchaseDate": raw.get("purchaseDate"),
                "lastUpdateDate": raw.get("updateTime") or raw.get("lastUpdateDate"),
            }

    if not order_map:
        item_order_ids = []
        for item in package_items:
            order_id = _clean_text(
                item.get("amazonOrderId") or item.get("orderNo") or item.get("orderId")
            )
            if order_id and order_id not in item_order_ids:
                item_order_ids.append(order_id)
        for order_id in item_order_ids:
            order_map[order_id] = {
                "amazonOrderId": order_id,
                "purchaseDate": raw.get("purchaseDate"),
                "lastUpdateDate": raw.get("updateTime") or raw.get("lastUpdateDate"),
            }
    return order_map


def _group_items_by_order(
    package_items: list[dict[str, Any]],
    order_map: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sole_order_id = next(iter(order_map)) if len(order_map) == 1 else None
    for item in package_items:
        amazon_order_id = _clean_text(
            item.get("amazonOrderId") or item.get("orderNo") or item.get("orderId")
        )
        if not amazon_order_id:
            amazon_order_id = sole_order_id
        if not amazon_order_id or amazon_order_id not in order_map:
            logger.warning(
                "package_ship_item_skipped_missing_order_id",
                amazon_order_id=amazon_order_id,
            )
            continue
        grouped[amazon_order_id].append(item)
    return dict(grouped)


def _extract_package_orders(raw: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("orders", "orderList", "orderInfoList", "orderInfos", "packageOrderList"):
        value = raw.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _extract_package_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("items", "itemList", "packageItemList", "orderItemList", "skuInfoVo", "details"):
        value = raw.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _resolve_package_country(
    raw: dict[str, Any],
    *,
    shop_id: str,
    package_sn: str,
    platform_name: str,
    eu_countries: set[str],
) -> tuple[str, str | None]:
    country_raw = raw.get("marketplace")
    country = normalize_observed_country_code(country_raw)
    if country is not None:
        mapped = apply_eu_mapping(country, eu_countries)
        return mapped or country, country

    fallback = normalize_source_country_or_unknown(
        country_raw,
        event="package_ship_order_country_unrecognized",
        shop_id=shop_id,
        package_sn=package_sn,
        platform_name=platform_name,
    )
    return fallback, None


def _parse_order_date(raw: Any, fallback: Any, marketplace_id: str) -> datetime:
    parsed = parse_saihu_time(_clean_text(raw), marketplace_id)
    if parsed is not None:
        return parsed
    fallback_parsed = parse_saihu_time(_clean_text(fallback), marketplace_id)
    return fallback_parsed or now_beijing()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_decimal(value: Any) -> Any:
    if value is None or value == "":
        return None
    from decimal import Decimal, InvalidOperation

    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
