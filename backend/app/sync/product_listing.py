"""Sync online product listings from Saihu."""

from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.country_mapping import apply_eu_mapping, load_eu_countries
from app.core.exceptions import ValidationFailed
from app.core.logging import get_logger
from app.core.timezone import marketplace_to_country, now_beijing
from app.db.session import async_session_factory
from app.models.product_listing import ProductListing
from app.models.sku import SkuConfig
from app.saihu.endpoints.product_listing import list_product_listings
from app.sync.common import mark_sync_failed, mark_sync_running, mark_sync_success
from app.tasks.jobs import JobContext, register

logger = get_logger(__name__)
JOB_NAME = "sync_product_listing"
_UNMATCHED_LISTING_NULLABLE_COLUMNS = ("commodity_sku", "commodity_id")


@register(JOB_NAME)
async def sync_product_listing_job(ctx: JobContext) -> None:
    await ctx.progress(current_step="开始同步在线产品信息", total_steps=1)
    async with async_session_factory() as db:
        started = await mark_sync_running(db, JOB_NAME)

    inserted = 0
    try:
        async with async_session_factory() as db:
            await _ensure_product_listing_schema_compatible(db)
            eu_countries = await load_eu_countries(db)

        async def _report_page(page_no: int, total_page: int, rows_count: int) -> None:
            if total_page <= 0:
                return
            await ctx.progress(
                total_steps=total_page,
                step_detail=f"第 {page_no} / {total_page} 页，当前页 {rows_count} 条，已处理 {inserted} 条",
            )

        async with async_session_factory() as db:
            async for raw in list_product_listings(
                only_matched=False,
                only_active=False,
                on_page=_report_page,
            ):
                await _upsert_listing(db, raw, eu_countries)
                inserted += 1
            created_sku_configs = await _backfill_sku_configs_from_synced_listings(db)
            await db.commit()

        async with async_session_factory() as db:
            await mark_sync_success(db, JOB_NAME, started)
        logger.info(
            "sync_product_listing_done",
            count=inserted,
            sku_config_created=created_sku_configs,
        )
        await ctx.progress(current_step="完成", step_detail=f"共 {inserted} 条 listing")
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
        str(row["column_name"]): str(row["is_nullable"]).upper() == "YES"
        for row in rows
    }
    incompatible = [
        column for column in _UNMATCHED_LISTING_NULLABLE_COLUMNS if nullable_map.get(column) is not True
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


def _infer_is_matched(raw: dict[str, Any]) -> bool:
    return bool(_normalize_optional_text(raw.get("commodityId"))) and bool(
        _normalize_optional_text(raw.get("commoditySku"))
    )


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
            k: v for k, v in values.items() if k not in ("shop_id", "marketplace_id", "seller_sku")
        },
    )
    await db.execute(stmt)


async def _backfill_sku_configs_from_synced_listings(db: AsyncSession) -> int:
    sku_rows = (
        (
            await db.execute(
                select(
                    ProductListing.commodity_sku,
                    ProductListing.is_matched,
                    ProductListing.online_status,
                )
                .where(ProductListing.commodity_sku.is_not(None))
                .order_by(ProductListing.commodity_sku)
            )
        )
        .all()
    )
    if not sku_rows:
        return 0
    sku_enabled_map: dict[str, bool] = {}
    for commodity_sku, is_matched, online_status in sku_rows:
        if commodity_sku is None:
            continue
        sku_enabled_map[commodity_sku] = sku_enabled_map.get(commodity_sku, False) or (
            bool(is_matched) and str(online_status or "").strip().lower() == "active"
        )
    sku_codes = sorted(sku_enabled_map)

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
            [{"commodity_sku": code, "enabled": sku_enabled_map[code]} for code in missing_codes]
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
