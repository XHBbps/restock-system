"""简易 metrics 端点(非 Prometheus,文本格式)。

返回 task_run 各状态计数 + 最近 24h 同步成功率,用于人工巡检。
"""

from datetime import timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_session
from app.core.timezone import now_beijing
from app.models.api_call_log import ApiCallLog
from app.models.task_run import TaskRun


# --------------- Dashboard schemas ---------------


class CountryStockDays(BaseModel):
    country: str
    avg_sale_days: float
    sku_count: int


class UrgentSkuItem(BaseModel):
    commodity_sku: str
    commodity_name: str | None = None
    main_image: str | None = None
    total_qty: int
    country_breakdown: dict[str, int]


class DashboardOverview(BaseModel):
    enabled_sku_count: int
    suggestion_item_count: int
    pushed_count: int
    urgent_count: int
    suggestion_id: int | None
    suggestion_status: str | None
    target_days: int
    country_stock_days: list[CountryStockDays]
    top_urgent_skus: list[UrgentSkuItem]

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("", response_class=PlainTextResponse)
async def metrics(
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> str:
    # task_run 状态分布
    rows = (
        await db.execute(select(TaskRun.status, func.count()).group_by(TaskRun.status))
    ).all()
    task_status_lines = [f"task_run_status{{status=\"{s}\"}} {n}" for s, n in rows]

    # 24h 同步成功率
    since = now_beijing() - timedelta(hours=24)
    api_rows = (
        await db.execute(
            select(
                func.count().label("total"),
                func.sum(case((ApiCallLog.saihu_code == 0, 1), else_=0)).label("succ"),
            ).where(ApiCallLog.called_at >= since)
        )
    ).one()
    total = int(api_rows[0] or 0)
    succ = int(api_rows[1] or 0)
    rate = (succ / total) if total else 0.0

    lines = [
        "# HELP task_run_status TaskRun count by status",
        "# TYPE task_run_status gauge",
        *task_status_lines,
        "",
        "# HELP saihu_api_calls_24h Total Saihu API calls in last 24h",
        "# TYPE saihu_api_calls_24h gauge",
        f"saihu_api_calls_24h {total}",
        "",
        "# HELP saihu_api_success_rate_24h Success rate of Saihu API calls",
        "# TYPE saihu_api_success_rate_24h gauge",
        f"saihu_api_success_rate_24h {rate:.4f}",
        "",
    ]
    return "\n".join(lines)


@router.get("/dashboard", response_model=DashboardOverview)
async def get_dashboard_overview(
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> DashboardOverview:
    from app.models.global_config import GlobalConfig
    from app.models.sku import SkuConfig
    from app.models.suggestion import Suggestion, SuggestionItem

    # 1. Enabled SKU count
    enabled_sku_count = (
        await db.execute(select(func.count()).where(SkuConfig.enabled.is_(True)))
    ).scalar_one()

    # 2. Global config target_days
    config = (
        await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
    ).scalar_one_or_none()
    target_days = config.target_days if config else 60

    # 3. Current suggestion (latest draft or partial)
    suggestion = (
        await db.execute(
            select(Suggestion)
            .where(Suggestion.status.in_(["draft", "partial"]))
            .order_by(Suggestion.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if not suggestion:
        return DashboardOverview(
            enabled_sku_count=int(enabled_sku_count or 0),
            suggestion_item_count=0,
            pushed_count=0,
            urgent_count=0,
            suggestion_id=None,
            suggestion_status=None,
            target_days=target_days,
            country_stock_days=[],
            top_urgent_skus=[],
        )

    # 4. Load all suggestion items
    items = (
        await db.execute(
            select(SuggestionItem).where(SuggestionItem.suggestion_id == suggestion.id)
        )
    ).scalars().all()

    pushed_count = sum(1 for it in items if it.push_status == "pushed")
    urgent_count = sum(1 for it in items if it.urgent)

    # 5. Aggregate sale_days by country from snapshots
    country_days: dict[str, list[float]] = {}
    for it in items:
        if not it.sale_days_snapshot:
            continue
        for country, days_val in it.sale_days_snapshot.items():
            if isinstance(days_val, (int, float)) and days_val >= 0:
                country_days.setdefault(country, []).append(float(days_val))

    country_stock_days = sorted(
        [
            CountryStockDays(
                country=c,
                avg_sale_days=round(sum(vals) / len(vals), 1),
                sku_count=len(vals),
            )
            for c, vals in country_days.items()
        ],
        key=lambda x: x.avg_sale_days,
    )

    # 6. Top 10 urgent SKUs by total_qty
    from app.models.product_listing import ProductListing

    urgent_items = sorted(
        [it for it in items if it.urgent],
        key=lambda it: it.total_qty,
        reverse=True,
    )[:10]

    # Batch-load product names and images for urgent SKUs
    urgent_sku_codes = [it.commodity_sku for it in urgent_items]
    name_map: dict[str, tuple[str | None, str | None]] = {}
    if urgent_sku_codes:
        listing_rows = (
            await db.execute(
                select(
                    ProductListing.commodity_sku,
                    ProductListing.commodity_name,
                    ProductListing.main_image,
                ).where(ProductListing.commodity_sku.in_(urgent_sku_codes))
            )
        ).all()
        for sku, name, img in listing_rows:
            if sku not in name_map:
                name_map[sku] = (name, img)

    top_urgent_skus = [
        UrgentSkuItem(
            commodity_sku=it.commodity_sku,
            commodity_name=(name_map.get(it.commodity_sku) or (None, None))[0],
            main_image=(name_map.get(it.commodity_sku) or (None, None))[1],
            total_qty=it.total_qty,
            country_breakdown={
                k: int(v) for k, v in (it.country_breakdown or {}).items()
            },
        )
        for it in urgent_items
    ]

    return DashboardOverview(
        enabled_sku_count=int(enabled_sku_count or 0),
        suggestion_item_count=len(items),
        pushed_count=pushed_count,
        urgent_count=urgent_count,
        suggestion_id=suggestion.id,
        suggestion_status=suggestion.status,
        target_days=target_days,
        country_stock_days=country_stock_days,
        top_urgent_skus=top_urgent_skus,
    )
