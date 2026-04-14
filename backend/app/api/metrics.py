"""简易 metrics 端点(非 Prometheus,文本格式)。

返回 task_run 各状态计数 + 最近 24h 同步成功率,用于人工巡检。
"""

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_session
from app.core.restock_regions import resolve_allowed_restock_regions
from app.core.timezone import now_beijing
from app.engine.step1_velocity import run_step1
from app.engine.step2_sale_days import run_step2
from app.engine.step3_country_qty import compute_country_qty
from app.models.api_call_log import ApiCallLog
from app.models.product_listing import ProductListing
from app.models.task_run import TaskRun

# --------------- Dashboard schemas ---------------


class CountryRiskDistribution(BaseModel):
    country: str
    urgent_count: int
    warning_count: int
    safe_count: int
    total_count: int


class UrgentSkuItem(BaseModel):
    commodity_sku: str
    commodity_name: str | None = None
    main_image: str | None = None
    country: str
    sale_days: float | None = None


class CountryRestockDistribution(BaseModel):
    country: str
    total_qty: int


class DashboardOverview(BaseModel):
    enabled_sku_count: int
    suggestion_item_count: int
    pushed_count: int
    urgent_count: int
    warning_count: int
    safe_count: int
    risk_country_count: int
    suggestion_id: int | None
    suggestion_status: str | None
    lead_time_days: int
    target_days: int
    country_risk_distribution: list[CountryRiskDistribution]
    country_restock_distribution: list[CountryRestockDistribution]
    top_urgent_skus: list[UrgentSkuItem]


router = APIRouter(prefix="/api/metrics", tags=["metrics"])


def _country_sale_days(snapshot: dict[str, Any] | None, country: str) -> float | None:
    if not snapshot:
        return None
    raw = snapshot.get(country)
    return float(raw) if isinstance(raw, (int, float)) else None


def _build_country_risk_distribution(
    sale_days_by_sku: dict[str, dict[str, float]],
    *,
    lead_time_days: int,
    target_days: int,
) -> tuple[list[CountryRiskDistribution], int, int, int]:
    country_risk_counts: dict[str, dict[str, int]] = {}
    urgent_count = 0
    warning_count = 0
    safe_count = 0

    for country_map in sale_days_by_sku.values():
        for country, days_val in country_map.items():
            if not isinstance(days_val, (int, float)) or days_val < 0:
                continue
            counts = country_risk_counts.setdefault(
                country,
                {"urgent_count": 0, "warning_count": 0, "safe_count": 0},
            )
            if float(days_val) < lead_time_days:
                counts["urgent_count"] += 1
                urgent_count += 1
            elif float(days_val) < target_days:
                counts["warning_count"] += 1
                warning_count += 1
            else:
                counts["safe_count"] += 1
                safe_count += 1

    distribution = sorted(
        [
            CountryRiskDistribution(
                country=country,
                urgent_count=counts["urgent_count"],
                warning_count=counts["warning_count"],
                safe_count=counts["safe_count"],
                total_count=(
                    counts["urgent_count"] + counts["warning_count"] + counts["safe_count"]
                ),
            )
            for country, counts in country_risk_counts.items()
        ],
        key=lambda item: item.country,
    )
    return distribution, urgent_count, warning_count, safe_count


async def _load_product_listing_map(
    db: AsyncSession,
    commodity_skus: list[str],
) -> dict[str, tuple[str | None, str | None]]:
    name_map: dict[str, tuple[str | None, str | None]] = {}
    if not commodity_skus:
        return name_map

    listing_rows = (
        await db.execute(
            select(
                ProductListing.commodity_sku,
                ProductListing.commodity_name,
                ProductListing.main_image,
            ).where(ProductListing.commodity_sku.in_(commodity_skus))
        )
    ).all()
    for sku, name, img in listing_rows:
        if sku not in name_map:
            name_map[sku] = (name, img)
    return name_map


async def _build_top_urgent_skus(
    db: AsyncSession,
    *,
    sale_days_by_sku: dict[str, dict[str, float]],
    country_qty_by_sku: dict[str, dict[str, int]],
    lead_time_days: int,
) -> list[UrgentSkuItem]:
    urgent_rows: list[tuple[str, str, float]] = []
    for sku, country_qty in country_qty_by_sku.items():
        for country, qty in country_qty.items():
            if qty <= 0:
                continue
            sale_days = _country_sale_days(sale_days_by_sku.get(sku), country)
            if sale_days is None or sale_days > lead_time_days:
                continue
            urgent_rows.append((sku, country, sale_days))

    urgent_rows = sorted(
        urgent_rows,
        key=lambda row: (row[2], row[0], row[1]),
    )[:10]

    name_map = await _load_product_listing_map(
        db,
        list(dict.fromkeys(sku for sku, _, _ in urgent_rows)),
    )
    return [
        UrgentSkuItem(
            commodity_sku=sku,
            commodity_name=(name_map.get(sku) or (None, None))[0],
            main_image=(name_map.get(sku) or (None, None))[1],
            country=country,
            sale_days=round(sale_days, 1),
        )
        for sku, country, sale_days in urgent_rows
    ]


@router.get("", response_class=PlainTextResponse)
async def metrics(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> str:
    # task_run 状态分布
    rows = (await db.execute(select(TaskRun.status, func.count()).group_by(TaskRun.status))).all()
    task_status_lines = [f'task_run_status{{status="{s}"}} {n}' for s, n in rows]

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
    _: dict[str, Any] = Depends(get_current_session),
) -> DashboardOverview:
    from app.models.global_config import GlobalConfig
    from app.models.sku import SkuConfig
    from app.models.suggestion import Suggestion, SuggestionItem

    # 1. Enabled SKU list
    enabled_skus = (
        await db.execute(
            select(SkuConfig.commodity_sku)
            .where(SkuConfig.enabled.is_(True))
            .order_by(SkuConfig.commodity_sku)
        )
    ).scalars().all()
    enabled_sku_count = len(enabled_skus)

    # 2. Global config target_days
    config = (
        await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
    ).scalar_one_or_none()
    target_days = config.target_days if config else 60
    lead_time_days = config.lead_time_days if config else 50
    allowed_countries = resolve_allowed_restock_regions(config.restock_regions if config else [])

    velocity = (
        await run_step1(
            db,
            enabled_skus,
            now_beijing().date(),
            allowed_countries=allowed_countries,
        )
        if enabled_skus
        else {}
    )
    all_sale_days, inventory = await run_step2(db, velocity, enabled_skus) if enabled_skus else ({}, {})
    live_country_qty = compute_country_qty(velocity, inventory, target_days) if enabled_skus else {}
    country_risk_distribution, urgent_count, warning_count, safe_count = (
        _build_country_risk_distribution(
            all_sale_days,
            lead_time_days=lead_time_days,
            target_days=target_days,
        )
        if enabled_skus
        else ([], 0, 0, 0)
    )
    top_urgent_skus = (
        await _build_top_urgent_skus(
            db,
            sale_days_by_sku=all_sale_days,
            country_qty_by_sku=live_country_qty,
            lead_time_days=lead_time_days,
        )
        if enabled_skus
        else []
    )

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
            enabled_sku_count=enabled_sku_count,
            suggestion_item_count=0,
            pushed_count=0,
            urgent_count=urgent_count,
            warning_count=warning_count,
            safe_count=safe_count,
            risk_country_count=len(country_risk_distribution),
            suggestion_id=None,
            suggestion_status=None,
            lead_time_days=lead_time_days,
            target_days=target_days,
            country_risk_distribution=country_risk_distribution,
            country_restock_distribution=[],
            top_urgent_skus=top_urgent_skus,
        )

    # 4. Load all suggestion items
    items = (
        (
            await db.execute(
                select(SuggestionItem).where(SuggestionItem.suggestion_id == suggestion.id)
            )
        )
        .scalars()
        .all()
    )

    pushed_count = sum(1 for it in items if it.push_status == "pushed")

    # 5. Aggregate suggestion-only restock totals.
    country_restock_totals: dict[str, int] = {}
    for it in items:
        for country, qty in (it.country_breakdown or {}).items():
            if isinstance(qty, (int, float)) and qty > 0:
                country_restock_totals[country] = country_restock_totals.get(country, 0) + int(qty)
    country_restock_distribution = sorted(
        [
            CountryRestockDistribution(country=country, total_qty=qty)
            for country, qty in country_restock_totals.items()
        ],
        key=lambda item: (-item.total_qty, item.country),
    )

    return DashboardOverview(
        enabled_sku_count=enabled_sku_count,
        suggestion_item_count=len(items),
        pushed_count=pushed_count,
        urgent_count=urgent_count,
        warning_count=warning_count,
        safe_count=safe_count,
        risk_country_count=len(country_risk_distribution),
        suggestion_id=suggestion.id,
        suggestion_status=suggestion.status,
        lead_time_days=lead_time_days,
        target_days=target_days,
        country_risk_distribution=country_risk_distribution,
        country_restock_distribution=country_restock_distribution,
        top_urgent_skus=top_urgent_skus,
    )
