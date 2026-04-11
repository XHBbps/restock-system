"""Incremental sync for order details.

Strategy:
- Fetch details only for orders related to matched SKUs
- Skip orders already recorded in ``order_detail_fetch_log``
- Respect the endpoint's low QPS limit

Current business rule:
- Address fields from Saihu order detail are not used and are stored as null
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SaihuBizError
from app.core.logging import get_logger
from app.core.timezone import marketplace_to_country, now_beijing
from app.db.session import async_session_factory
from app.models.order import OrderDetail, OrderDetailFetchLog, OrderHeader, OrderItem
from app.models.product_listing import ProductListing
from app.saihu.endpoints.order_detail import get_order_detail
from app.sync.common import mark_sync_failed, mark_sync_running, mark_sync_success
from app.tasks.jobs import JobContext, register

logger = get_logger(__name__)
JOB_NAME = "sync_order_detail"
MAX_PER_RUN = 500


CONCURRENCY = 3  # 与 rate_limit 中 order_detail 的 QPS 一致


def _is_permanent_saihu_error(exc: BaseException) -> bool:
    """Classify whether ``exc`` should be recorded as a permanent fetch failure.

    Only :class:`SaihuBizError` represents real business-level errors (invalid
    order id, closed shop, malformed response, etc.) that will never succeed
    on retry. Rate-limited / network / auth-expired errors bubble up only
    after the client-level tenacity budget is exhausted but a later run may
    still succeed, so they must NOT be written to ``order_detail_fetch_log``.
    Any other exception type is also treated as transient and left for the
    next run (matches historical behavior for non-Saihu errors).
    """
    return isinstance(exc, SaihuBizError)


@register(JOB_NAME)
async def sync_order_detail_job(ctx: JobContext) -> None:
    import asyncio

    await ctx.progress(current_step="同步订单详情", total_steps=1)
    async with async_session_factory() as db:
        started = await mark_sync_running(db, JOB_NAME)

    fetched = 0
    failed = 0
    sem = asyncio.Semaphore(CONCURRENCY)

    async def _fetch_one(shop_id: str, amazon_order_id: str) -> bool:
        async with sem:
            try:
                detail = await get_order_detail(shop_id=shop_id, amazon_order_id=amazon_order_id)
                async with async_session_factory() as db:
                    await _save_detail(db, shop_id, amazon_order_id, detail)
                    await db.commit()
                return True
            except Exception as exc:
                if _is_permanent_saihu_error(exc):
                    # Only SaihuBizError reaches here — record as permanent so
                    # _find_pending_orders will skip this order on future runs.
                    assert isinstance(exc, SaihuBizError)  # narrows type for _log_fetch_failure
                    async with async_session_factory() as db:
                        await _log_fetch_failure(db, shop_id, amazon_order_id, exc)
                        await db.commit()
                    logger.warning(
                        "order_detail_fetch_permanent_failure",
                        shop_id=shop_id,
                        amazon_order_id=amazon_order_id,
                        saihu_code=exc.code,
                        error=str(exc),
                    )
                else:
                    # Transient: rate limited, network, auth expired, or non-Saihu
                    # exception. Don't persist — next sync run will pick this order
                    # up again via _find_pending_orders.
                    logger.warning(
                        "order_detail_fetch_transient_failure",
                        shop_id=shop_id,
                        amazon_order_id=amazon_order_id,
                        error=str(exc),
                    )
                return False

    try:
        async with async_session_factory() as db:
            targets = await _find_pending_orders(db, MAX_PER_RUN)
            await ctx.progress(step_detail=f"待拉取 {len(targets)} 条")

        # 分批并发，每批 CONCURRENCY 个
        for i in range(0, len(targets), CONCURRENCY):
            batch = targets[i : i + CONCURRENCY]
            results = await asyncio.gather(
                *[_fetch_one(sid, oid) for sid, oid in batch]
            )
            for ok in results:
                if ok:
                    fetched += 1
                else:
                    failed += 1
            if (fetched + failed) % 20 == 0:
                await ctx.progress(step_detail=f"已拉 {fetched} / 失败 {failed}")

        async with async_session_factory() as db:
            await mark_sync_success(db, JOB_NAME, started)
        logger.info("sync_order_detail_done", fetched=fetched, failed=failed)
        await ctx.progress(current_step="完成", step_detail=f"成功 {fetched} / 失败 {failed}")
    except Exception as exc:
        async with async_session_factory() as db:
            await mark_sync_failed(db, JOB_NAME, str(exc))
        raise


async def _find_pending_orders(db: AsyncSession, limit: int) -> list[tuple[str, str]]:
    matched_subq = (
        select(ProductListing.shop_id, ProductListing.seller_sku)
        .where(ProductListing.is_matched.is_(True))
        .where(ProductListing.seller_sku.is_not(None))
        .subquery()
    )

    stmt = (
        select(
            OrderHeader.shop_id,
            OrderHeader.amazon_order_id,
            OrderHeader.purchase_date,
        )
        .join(OrderItem, OrderItem.order_id == OrderHeader.id)
        .join(
            matched_subq,
            (matched_subq.c.shop_id == OrderHeader.shop_id)
            & (matched_subq.c.seller_sku == OrderItem.seller_sku),
        )
        .outerjoin(
            OrderDetailFetchLog,
            (OrderDetailFetchLog.shop_id == OrderHeader.shop_id)
            & (OrderDetailFetchLog.amazon_order_id == OrderHeader.amazon_order_id),
        )
        .where(OrderDetailFetchLog.amazon_order_id.is_(None))
        .distinct()
        .order_by(OrderHeader.purchase_date.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [(r[0], r[1]) for r in rows]


def _sanitize_detail_country(detail: dict[str, object]) -> str | None:
    marketplace_id_raw = detail.get("marketplaceId") or ""
    return marketplace_to_country(marketplace_id_raw)


def _postal_code_for_routing(detail: dict[str, object]) -> str | None:
    raw = detail.get("postalCode")
    if raw is None:
        return None
    postal_code = str(raw).strip()
    return postal_code or None


def _disabled_address_fields() -> dict[str, None]:
    return {
        "state_or_region": None,
        "city": None,
        "detail_address": None,
        "receiver_name": None,
    }


async def _save_detail(
    db: AsyncSession,
    shop_id: str,
    amazon_order_id: str,
    detail: dict[str, object],
) -> None:
    detail_values = {
        "shop_id": shop_id,
        "amazon_order_id": amazon_order_id,
        "postal_code": _postal_code_for_routing(detail),
        "country_code": _sanitize_detail_country(detail),
        "fetched_at": now_beijing(),
        **_disabled_address_fields(),
    }
    stmt = pg_insert(OrderDetail).values(**detail_values)
    stmt = stmt.on_conflict_do_update(
        constraint="pk_order_detail",
        set_={k: v for k, v in detail_values.items() if k not in ("shop_id", "amazon_order_id")},
    )
    await db.execute(stmt)

    log_values = {
        "shop_id": shop_id,
        "amazon_order_id": amazon_order_id,
        "fetched_at": now_beijing(),
        "http_status": 200,
        "saihu_code": 0,
        "saihu_msg": None,
    }
    log_stmt = pg_insert(OrderDetailFetchLog).values(**log_values)
    log_stmt = log_stmt.on_conflict_do_nothing(constraint="pk_order_detail_fetch_log")
    await db.execute(log_stmt)


async def _log_fetch_failure(
    db: AsyncSession,
    shop_id: str,
    amazon_order_id: str,
    exc: SaihuBizError,
) -> None:
    log_values = {
        "shop_id": shop_id,
        "amazon_order_id": amazon_order_id,
        "fetched_at": now_beijing(),
        "http_status": None,
        "saihu_code": exc.code,
        "saihu_msg": str(exc.message)[:1000],
    }
    stmt = pg_insert(OrderDetailFetchLog).values(**log_values)
    stmt = stmt.on_conflict_do_nothing(constraint="pk_order_detail_fetch_log")
    await db.execute(stmt)
