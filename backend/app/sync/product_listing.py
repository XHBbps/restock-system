"""Sync Saihu commodity master data and online product listings."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.country_mapping import apply_eu_mapping, load_eu_countries
from app.core.exceptions import ValidationFailed
from app.core.logging import get_logger
from app.core.timezone import marketplace_to_country, now_beijing
from app.db.session import async_session_factory
from app.models.commodity import CommodityMaster
from app.models.product_listing import ProductListing
from app.models.sku import SkuConfig
from app.saihu.endpoints.commodity import list_commodities
from app.saihu.endpoints.product_listing import list_product_listings
from app.sync.common import mark_sync_failed, mark_sync_running, mark_sync_success
from app.tasks.jobs import JobContext, register

logger = get_logger(__name__)
JOB_NAME = "sync_product_listing"
_UNMATCHED_LISTING_NULLABLE_COLUMNS = ("commodity_sku", "commodity_id")


@register(JOB_NAME)
async def sync_product_listing_job(ctx: JobContext) -> None:
    await ctx.progress(current_step="同步商品主数据", total_steps=2)
    async with async_session_factory() as db:
        started = await mark_sync_running(db, JOB_NAME)

    commodity_count = 0
    listing_count = 0
    try:
        async with async_session_factory() as db:
            await _ensure_product_listing_schema_compatible(db)
            eu_countries = await load_eu_countries(db)

        async def _report_commodity_page(page_no: int, total_page: int, rows_count: int) -> None:
            if total_page <= 0:
                return
            await ctx.progress(
                total_steps=total_page,
                step_detail=(
                    f"商品主数据第 {page_no} / {total_page} 页，"
                    f"当前页 {rows_count} 条，已处理 {commodity_count} 条"
                ),
            )

        async with async_session_factory() as db:
            async for raw in list_commodities(on_page=_report_commodity_page):
                if await _upsert_commodity(db, raw):
                    commodity_count += 1
            created_commodity_sku_configs = await _backfill_sku_configs_from_commodities(db)
            await db.commit()

        async def _report_listing_page(page_no: int, total_page: int, rows_count: int) -> None:
            if total_page <= 0:
                return
            await ctx.progress(
                total_steps=total_page,
                step_detail=(
                    f"在线产品 listing 第 {page_no} / {total_page} 页，"
                    f"当前页 {rows_count} 条，已处理 {listing_count} 条"
                ),
            )

        async with async_session_factory() as db:
            async for raw in list_product_listings(
                only_matched=False,
                only_active=False,
                on_page=_report_listing_page,
            ):
                await _upsert_listing(db, raw, eu_countries)
                listing_count += 1
            created_listing_sku_configs = await _backfill_sku_configs_from_synced_listings(db)
            await db.commit()

        async with async_session_factory() as db:
            await mark_sync_success(db, JOB_NAME, started)
        logger.info(
            "sync_product_listing_done",
            commodity_count=commodity_count,
            listing_count=listing_count,
            commodity_sku_config_created=created_commodity_sku_configs,
            listing_sku_config_created=created_listing_sku_configs,
        )
        await ctx.progress(
            current_step="完成",
            step_detail=f"商品主数据 {commodity_count} 条，listing {listing_count} 条",
        )
    except Exception as exc:
        async with async_session_factory() as db:
            await mark_sync_failed(db, JOB_NAME, str(exc))
        raise


async def _ensure_product_listing_schema_compatible(db: AsyncSession) -> None:
    result = await db.execute(
        text(
            """
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'product_listing'
              AND column_name IN ('commodity_sku', 'commodity_id')
            """
        )
    )
    rows = result.mappings().all()
    nullable_map = {
        str(row["column_name"]): str(row["is_nullable"]).upper() == "YES" for row in rows
    }
    incompatible = [
        column
        for column in _UNMATCHED_LISTING_NULLABLE_COLUMNS
        if nullable_map.get(column) is not True
    ]
    if incompatible:
        columns = ", ".join(incompatible)
        raise ValidationFailed(
            "\u6570\u636e\u5e93 schema \u843d\u540e\u4e8e\u4ee3\u7801\uff1a"
            f"product_listing.{columns} \u4ecd\u672a\u5141\u8bb8 NULL\uff0c"
            "\u5546\u54c1\u540c\u6b65\u65e0\u6cd5\u4fdd\u5b58\u672a\u914d\u5bf9\u5546\u54c1\u3002"
            "\u8bf7\u5148\u6267\u884c `alembic upgrade head` "
            "\u5e94\u7528\u8fc1\u79fb `20260413_2230_allow_unmatched_product_listing`\u3002"
        )


def _normalize_online_status(status: Any) -> str:
    value = str(status or "").strip()
    if not value:
        return "active"
    return value.lower()


def _normalize_optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text_value = str(value or "").strip().lower()
    return text_value in {"1", "true", "yes", "y"}


def _normalize_child_skus(value: Any) -> list[Any] | None:
    if value is None or value == "":
        return None
    if isinstance(value, list):
        return value
    return [value]


def _infer_is_matched(raw: dict[str, Any]) -> bool:
    return bool(_normalize_optional_text(raw.get("commodityId"))) and bool(
        _normalize_optional_text(raw.get("commoditySku"))
    )


def _commodity_image_url(raw: dict[str, Any]) -> str | None:
    for field_name in ("imgUrl", "imageUrl", "mainImage"):
        image_url = _normalize_optional_text(raw.get(field_name))
        if image_url:
            return image_url
    return None


async def _upsert_commodity(db: AsyncSession, raw: dict[str, Any]) -> bool:
    sku = _normalize_optional_text(raw.get("sku"))
    if not sku:
        return False

    values = {
        "sku": sku,
        "commodity_id": _normalize_optional_text(raw.get("id")),
        "name": _normalize_optional_text(raw.get("name")),
        "state": _normalize_optional_text(raw.get("state")),
        "is_group": _to_bool(raw.get("isGroup")),
        "img_url": _commodity_image_url(raw),
        "purchase_days": _to_int(raw.get("purchaseDays")),
        "child_skus": _normalize_child_skus(raw.get("childSkus")),
        "last_sync_at": now_beijing(),
    }

    stmt = pg_insert(CommodityMaster).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["sku"],
        set_={key: value for key, value in values.items() if key != "sku"},
    )
    await db.execute(stmt)
    return True


async def _upsert_listing(
    db: AsyncSession,
    raw: dict[str, Any],
    eu_countries: set[str] | None = None,
) -> None:
    shop_id = _normalize_optional_text(raw.get("shopId"))
    marketplace_id_raw = _normalize_optional_text(raw.get("marketplaceId"))
    seller_sku = _normalize_optional_text(raw.get("sku"))
    if not shop_id or not marketplace_id_raw or not seller_sku:
        return

    commodity_sku = _normalize_optional_text(raw.get("commoditySku"))
    commodity_id = _normalize_optional_text(raw.get("commodityId"))
    mkt_normalized = marketplace_to_country(marketplace_id_raw) or marketplace_id_raw
    mapped_marketplace = apply_eu_mapping(mkt_normalized, eu_countries or set()) or mkt_normalized

    values = {
        "commodity_sku": commodity_sku,
        "commodity_id": commodity_id,
        "shop_id": shop_id,
        "marketplace_id": mapped_marketplace,
        "original_marketplace_id": (
            mkt_normalized if mapped_marketplace != mkt_normalized else None
        ),
        "seller_sku": seller_sku,
        "parent_sku": _normalize_optional_text(raw.get("parentSku")),
        "commodity_name": raw.get("title") or raw.get("commodityName"),
        "main_image": raw.get("mainImage"),
        "day7_sale_num": _to_int(raw.get("day7SaleNum")),
        "day14_sale_num": _to_int(raw.get("day14SaleNum")),
        "day30_sale_num": _to_int(raw.get("day30SaleNum")),
        "is_matched": _infer_is_matched(raw),
        "online_status": _normalize_online_status(raw.get("onlineStatus")),
        "last_sync_at": now_beijing(),
    }

    stmt = pg_insert(ProductListing).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["shop_id", "marketplace_id", "seller_sku"],
        set_={
            key: value
            for key, value in values.items()
            if key not in ("shop_id", "marketplace_id", "seller_sku")
        },
    )
    await db.execute(stmt)


async def _backfill_sku_configs_from_commodities(db: AsyncSession) -> int:
    sku_codes = sorted(
        (await db.execute(select(CommodityMaster.sku).order_by(CommodityMaster.sku)))
        .scalars()
        .all()
    )
    return await _insert_missing_sku_configs(db, sku_codes, enabled=True)


async def _backfill_sku_configs_from_synced_listings(db: AsyncSession) -> int:
    sku_codes = sorted(
        {
            sku
            for sku in (
                await db.execute(
                    select(ProductListing.commodity_sku)
                    .where(ProductListing.commodity_sku.is_not(None))
                    .order_by(ProductListing.commodity_sku)
                )
            )
            .scalars()
            .all()
            if sku is not None
        }
    )
    return await _insert_missing_sku_configs(db, sku_codes, enabled=True)


async def _insert_missing_sku_configs(
    db: AsyncSession,
    sku_codes: list[str],
    *,
    enabled: bool,
) -> int:
    if not sku_codes:
        return 0

    existing_codes = set(
        (
            await db.execute(
                select(SkuConfig.commodity_sku).where(SkuConfig.commodity_sku.in_(sku_codes))
            )
        )
        .scalars()
        .all()
    )
    missing_codes = [code for code in sku_codes if code not in existing_codes]
    if not missing_codes:
        return 0

    await db.execute(
        pg_insert(SkuConfig).values(
            [{"commodity_sku": code, "enabled": enabled} for code in missing_codes]
        )
    )
    return len(missing_codes)


def _to_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
