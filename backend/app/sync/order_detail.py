"""Incremental sync and manual refetch for order details."""

from datetime import timedelta

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
REFETCH_JOB_NAME = "refetch_order_detail"
MAX_PER_RUN = 500
DEFAULT_REFETCH_DAYS = 7
CONCURRENCY = 2


def _is_permanent_saihu_error(exc: BaseException) -> bool:
    """Return whether a fetch error should be recorded as permanent."""

    return isinstance(exc, SaihuBizError)


@register(JOB_NAME)
async def sync_order_detail_job(ctx: JobContext) -> None:
    async with async_session_factory() as db:
        targets = await _find_pending_orders(db, MAX_PER_RUN)
    await _run_fetch_job(ctx, job_name=JOB_NAME, targets=targets, step_label="订单详情同步")


@register(REFETCH_JOB_NAME)
async def refetch_order_detail_job(ctx: JobContext) -> None:
    targets = _extract_refetch_targets(ctx.payload)
    await _run_fetch_job(ctx, job_name=REFETCH_JOB_NAME, targets=targets, step_label="订单详情补拉")


async def _run_fetch_job(
    ctx: JobContext,
    *,
    job_name: str,
    targets: list[tuple[str, str]],
    step_label: str,
) -> None:
    import asyncio

    await ctx.progress(current_step=step_label, total_steps=1)
    async with async_session_factory() as db:
        started = await mark_sync_running(db, job_name)

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
                    assert isinstance(exc, SaihuBizError)
                    async with async_session_factory() as db:
                        await _log_fetch_failure(db, shop_id, amazon_order_id, exc)
                        await db.commit()
                    logger.warning(
                        "order_detail_fetch_permanent_failure",
                        job_name=job_name,
                        shop_id=shop_id,
                        amazon_order_id=amazon_order_id,
                        saihu_code=exc.code,
                        error=str(exc),
                    )
                else:
                    logger.warning(
                        "order_detail_fetch_transient_failure",
                        job_name=job_name,
                        shop_id=shop_id,
                        amazon_order_id=amazon_order_id,
                        error=str(exc),
                    )
                return False

    try:
        await ctx.progress(step_detail=f"待处理 {len(targets)} 条")

        for index in range(0, len(targets), CONCURRENCY):
            batch = targets[index : index + CONCURRENCY]
            results = await asyncio.gather(*[_fetch_one(shop_id, amazon_order_id) for shop_id, amazon_order_id in batch])
            for ok in results:
                if ok:
                    fetched += 1
                else:
                    failed += 1
            if (fetched + failed) % 20 == 0:
                await ctx.progress(step_detail=f"已完成 {fetched} / 失败 {failed}")

        if failed:
            raise RuntimeError(f"{step_label}存在失败: success={fetched}, failed={failed}")

        async with async_session_factory() as db:
            await mark_sync_success(db, job_name, started)
        logger.info("order_detail_fetch_job_done", job_name=job_name, fetched=fetched, failed=failed)
        await ctx.progress(current_step="完成", step_detail=f"成功 {fetched} / 失败 {failed}")
    except Exception as exc:
        async with async_session_factory() as db:
            await mark_sync_failed(db, job_name, str(exc))
        raise


def _matched_listing_subquery():
    return (
        select(ProductListing.shop_id, ProductListing.seller_sku)
        .where(ProductListing.is_matched.is_(True))
        .where(ProductListing.seller_sku.is_not(None))
        .subquery()
    )


async def _find_pending_orders(db: AsyncSession, limit: int) -> list[tuple[str, str]]:
    matched_subq = _matched_listing_subquery()

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
    return [(row[0], row[1]) for row in rows]


async def find_refetch_targets(
    db: AsyncSession,
    *,
    days: int,
    limit: int,
    shop_id: str | None = None,
) -> list[tuple[str, str]]:
    matched_subq = _matched_listing_subquery()
    cutoff = now_beijing() - timedelta(days=days)

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
            OrderDetail,
            (OrderDetail.shop_id == OrderHeader.shop_id)
            & (OrderDetail.amazon_order_id == OrderHeader.amazon_order_id),
        )
        .where(OrderDetail.amazon_order_id.is_(None))
        .where(OrderHeader.purchase_date >= cutoff)
        .distinct()
        .order_by(OrderHeader.purchase_date.desc())
        .limit(limit)
    )
    if shop_id:
        stmt = stmt.where(OrderHeader.shop_id == shop_id)

    rows = (await db.execute(stmt)).all()
    return [(row[0], row[1]) for row in rows]


def serialize_refetch_targets(targets: list[tuple[str, str]]) -> list[dict[str, str]]:
    return [
        {"shop_id": shop_id, "amazon_order_id": amazon_order_id}
        for shop_id, amazon_order_id in targets
    ]


def _extract_refetch_targets(payload: dict[str, object]) -> list[tuple[str, str]]:
    raw_targets = payload.get("targets")
    if not isinstance(raw_targets, list):
        raise RuntimeError("订单详情补拉任务缺少 targets")

    targets: list[tuple[str, str]] = []
    for item in raw_targets:
        if not isinstance(item, dict):
            raise RuntimeError("订单详情补拉任务 targets 格式错误")
        shop_id = item.get("shop_id")
        amazon_order_id = item.get("amazon_order_id")
        if not isinstance(shop_id, str) or not isinstance(amazon_order_id, str):
            raise RuntimeError("订单详情补拉任务 targets 缺少订单主键")
        targets.append((shop_id, amazon_order_id))
    return targets


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
