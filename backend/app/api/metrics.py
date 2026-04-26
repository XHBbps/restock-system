"""简易 metrics 端点(非 Prometheus,文本格式)。

返回 task_run 各状态计数 + 最近 24h 同步成功率,用于人工巡检。
"""

from datetime import date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    UserContext,
    db_session,
    db_session_readonly,
    get_current_user,
    require_permission,
)
from app.core.permissions import HOME_REFRESH, HOME_VIEW, MONITOR_VIEW
from app.core.restock_regions import resolve_allowed_restock_regions
from app.core.timezone import now_beijing
from app.engine.context import CountryQtyMap, SaleDaysMap
from app.engine.step1_velocity import run_step1
from app.engine.step2_sale_days import run_step2
from app.engine.step3_country_qty import compute_country_qty
from app.engine.step4_total import compute_total, load_local_inventory
from app.models.api_call_log import ApiCallLog
from app.models.dashboard_snapshot import DashboardSnapshot
from app.models.product_listing import ProductListing
from app.models.task_run import TaskRun
from app.tasks.queue import enqueue_task

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


class DashboardOverviewPayload(BaseModel):
    enabled_sku_count: int
    restock_sku_count: int = 0
    no_restock_sku_count: int = 0
    suggestion_item_count: int
    exported_count: int = 0
    urgent_count: int
    warning_count: int
    safe_count: int
    risk_country_count: int
    suggestion_id: int | None
    suggestion_status: str | None
    suggestion_snapshot_count: int = 0
    lead_time_days: int
    target_days: int
    country_risk_distribution: list[CountryRiskDistribution]
    country_restock_distribution: list[CountryRestockDistribution]
    top_urgent_skus: list[UrgentSkuItem]


class DashboardOverview(DashboardOverviewPayload):
    snapshot_status: Literal["ready", "missing", "refreshing"] = "ready"
    snapshot_updated_at: datetime | None = None
    snapshot_task_id: int | None = None


class DashboardRefreshOut(BaseModel):
    task_id: int
    existing: bool


router = APIRouter(prefix="/api/metrics", tags=["metrics"])
REFRESH_DASHBOARD_JOB_NAME = "refresh_dashboard_snapshot"


def _country_sale_days(snapshot: dict[str, Any] | None, country: str) -> float | None:
    if not snapshot:
        return None
    raw = snapshot.get(country)
    return float(raw) if isinstance(raw, (int, float)) else None


def _build_country_risk_distribution(
    sale_days_by_sku: SaleDaysMap,
    *,
    lead_time_days: int,
    target_days: int,
    allowed_countries: set[str] | None = None,
) -> tuple[list[CountryRiskDistribution], int, int, int]:
    country_risk_counts: dict[str, dict[str, int]] = {}
    urgent_count = 0
    warning_count = 0
    safe_count = 0

    for country_map in sale_days_by_sku.values():
        for country, days_val in country_map.items():
            if allowed_countries is not None and country not in allowed_countries:
                continue
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
    sale_days_by_sku: SaleDaysMap,
    country_qty_by_sku: CountryQtyMap,
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


def _has_restock_summary_keys(payload: dict[str, Any] | None) -> bool:
    return bool(payload and "restock_sku_count" in payload and "no_restock_sku_count" in payload)


def _empty_dashboard_payload(
    *,
    enabled_sku_count: int,
    lead_time_days: int,
    target_days: int,
) -> DashboardOverviewPayload:
    return DashboardOverviewPayload(
        enabled_sku_count=enabled_sku_count,
        restock_sku_count=0,
        no_restock_sku_count=enabled_sku_count,
        suggestion_item_count=0,
        exported_count=0,
        urgent_count=0,
        warning_count=0,
        safe_count=0,
        risk_country_count=0,
        suggestion_id=None,
        suggestion_status=None,
        suggestion_snapshot_count=0,
        lead_time_days=lead_time_days,
        target_days=target_days,
        country_risk_distribution=[],
        country_restock_distribution=[],
        top_urgent_skus=[],
    )


async def _get_active_dashboard_refresh_task(db: AsyncSession) -> TaskRun | None:
    result = await db.execute(
        select(TaskRun)
        .where(TaskRun.job_name == REFRESH_DASHBOARD_JOB_NAME)
        .where(TaskRun.status.in_(("pending", "running")))
        .order_by(TaskRun.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def build_dashboard_payload(db: AsyncSession) -> DashboardOverviewPayload:
    from app.models.global_config import GlobalConfig
    from app.models.sku import SkuConfig
    from app.models.suggestion import Suggestion, SuggestionItem
    from app.models.suggestion_snapshot import SuggestionSnapshot

    enabled_skus = list(
        (
            await db.execute(
                select(SkuConfig.commodity_sku)
                .where(SkuConfig.enabled.is_(True))
                .order_by(SkuConfig.commodity_sku)
            )
        )
        .scalars()
        .all()
    )
    enabled_sku_count = len(enabled_skus)

    config = (
        await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
    ).scalar_one_or_none()
    target_days = config.target_days if config else 60
    lead_time_days = config.lead_time_days if config else 50
    allowed_countries = resolve_allowed_restock_regions(config.restock_regions if config else [])

    suggestion = (
        await db.execute(
            select(Suggestion)
            .where(Suggestion.status == "draft")
            .order_by(Suggestion.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    demand_days = 0
    if suggestion:
        raw_demand_date = (getattr(suggestion, "global_config_snapshot", None) or {}).get(
            "demand_date"
        )
        if isinstance(raw_demand_date, str) and raw_demand_date:
            try:
                demand_days = max(
                    (date.fromisoformat(raw_demand_date) - now_beijing().date()).days,
                    0,
                )
            except ValueError:
                demand_days = 0
    effective_target_days = target_days + demand_days

    # velocity 口径与 runner 一致：不受 restock_regions 过滤，
    # 保证采购量公式里的 Σvelocity 覆盖全部销售国家（含白名单外）。
    velocity = await run_step1(db, enabled_skus, now_beijing().date()) if enabled_skus else {}
    all_sale_days, inventory = (
        await run_step2(db, velocity, enabled_skus) if enabled_skus else ({}, {})
    )
    live_country_qty_all = (
        compute_country_qty(velocity, inventory, effective_target_days) if enabled_skus else {}
    )
    # country_qty 只保留白名单国家（和 runner 行为一致）。
    if allowed_countries is not None:
        live_country_qty = {
            sku: {c: q for c, q in cq.items() if c in allowed_countries}
            for sku, cq in live_country_qty_all.items()
        }
    else:
        live_country_qty = live_country_qty_all
    local_stock = await load_local_inventory(db, enabled_skus) if enabled_skus else {}
    restock_sku_count = 0
    for sku in enabled_skus:
        sku_country_qty = live_country_qty.get(sku, {})
        if not sku_country_qty:
            continue
        total_qty = compute_total(
            sku=sku,
            country_qty_for_sku=sku_country_qty,
            velocity_for_sku=velocity.get(sku, {}),
            local_stock_for_sku=local_stock.get(sku),
            buffer_days=getattr(config, "buffer_days", 15) if config else 15,
            safety_stock_days=getattr(config, "safety_stock_days", 0) if config else 0,
        )
        if total_qty > 0:
            restock_sku_count += 1
    no_restock_sku_count = max(enabled_sku_count - restock_sku_count, 0)
    country_risk_distribution, urgent_count, warning_count, safe_count = (
        _build_country_risk_distribution(
            all_sale_days,
            lead_time_days=lead_time_days,
            target_days=target_days,
            allowed_countries=allowed_countries,
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

    if not suggestion:
        return DashboardOverviewPayload(
            enabled_sku_count=enabled_sku_count,
            restock_sku_count=restock_sku_count,
            no_restock_sku_count=no_restock_sku_count,
            suggestion_item_count=0,
            exported_count=0,
            urgent_count=urgent_count,
            warning_count=warning_count,
            safe_count=safe_count,
            risk_country_count=len(country_risk_distribution),
            suggestion_id=None,
            suggestion_status=None,
            suggestion_snapshot_count=0,
            lead_time_days=lead_time_days,
            target_days=target_days,
            country_risk_distribution=country_risk_distribution,
            country_restock_distribution=[],
            top_urgent_skus=top_urgent_skus,
        )

    items = (
        (
            await db.execute(
                select(SuggestionItem).where(SuggestionItem.suggestion_id == suggestion.id)
            )
        )
        .scalars()
        .all()
    )

    exported_count = sum(
        1
        for it in items
        if (
            getattr(it, "procurement_export_status", "pending") == "exported"
            or getattr(it, "restock_export_status", "pending") == "exported"
        )
    )
    suggestion_snapshot_count = (
        await db.execute(
            select(func.count())
            .select_from(SuggestionSnapshot)
            .where(SuggestionSnapshot.suggestion_id == suggestion.id)
        )
    ).scalar_one()
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

    return DashboardOverviewPayload(
        enabled_sku_count=enabled_sku_count,
        restock_sku_count=restock_sku_count,
        no_restock_sku_count=no_restock_sku_count,
        suggestion_item_count=len(items),
        exported_count=exported_count,
        urgent_count=urgent_count,
        warning_count=warning_count,
        safe_count=safe_count,
        risk_country_count=len(country_risk_distribution),
        suggestion_id=suggestion.id,
        suggestion_status=suggestion.status,
        suggestion_snapshot_count=int(suggestion_snapshot_count or 0),
        lead_time_days=lead_time_days,
        target_days=target_days,
        country_risk_distribution=country_risk_distribution,
        country_restock_distribution=country_restock_distribution,
        top_urgent_skus=top_urgent_skus,
    )


@router.get("", response_class=PlainTextResponse)
async def metrics(
    db: AsyncSession = Depends(db_session_readonly),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(HOME_VIEW)),
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


async def _ensure_dashboard_refresh_task(db: AsyncSession) -> TaskRun | None:
    """配置变更 stale 时自动 enqueue 一条 refresh 任务（dedupe 保证同时只一条）。"""
    task_id, _existing = await enqueue_task(
        db,
        job_name=REFRESH_DASHBOARD_JOB_NAME,
        trigger_source="scheduler",
        dedupe_key=REFRESH_DASHBOARD_JOB_NAME,
        payload={"triggered_by": "auto_stale"},
    )
    result = await db.execute(select(TaskRun).where(TaskRun.id == task_id))
    return result.scalar_one_or_none()


@router.get("/dashboard", response_model=DashboardOverview)
async def get_dashboard_overview(
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(HOME_VIEW)),
) -> DashboardOverview:
    active_task = await _get_active_dashboard_refresh_task(db)
    snapshot = (
        await db.execute(select(DashboardSnapshot).where(DashboardSnapshot.id == 1))
    ).scalar_one_or_none()

    # 配置变更 → dashboard_snapshot.stale=True，若无 refresh 任务活跃则自动 enqueue
    stale = bool(getattr(snapshot, "stale", False)) if snapshot is not None else False
    if stale and active_task is None:
        active_task = await _ensure_dashboard_refresh_task(db)

    if snapshot and snapshot.payload:
        try:
            payload = DashboardOverviewPayload.model_validate(snapshot.payload)
        except ValidationError:
            payload = _empty_dashboard_payload(
                enabled_sku_count=0, lead_time_days=50, target_days=60
            )
            return DashboardOverview(
                **payload.model_dump(),
                snapshot_status="refreshing" if active_task else "missing",
                snapshot_updated_at=snapshot.refreshed_at or snapshot.updated_at,
                snapshot_task_id=active_task.id if active_task else None,
            )
        # 旧快照缺少新增字段时，Pydantic 自动填充默认值（restock_sku_count=0 等）；
        # 同时入队刷新任务，后台更新快照后下次请求即为完整数据
        needs_refresh = not _has_restock_summary_keys(snapshot.payload)
        if (active_task is not None) or stale:
            status: Literal["ready", "missing", "refreshing"] = "refreshing"
        elif needs_refresh:
            status = "missing"
        else:
            status = "ready"
        return DashboardOverview(
            **payload.model_dump(),
            snapshot_status=status,
            snapshot_updated_at=snapshot.refreshed_at or snapshot.updated_at,
            snapshot_task_id=active_task.id if active_task else None,
        )

    payload = _empty_dashboard_payload(enabled_sku_count=0, lead_time_days=50, target_days=60)
    return DashboardOverview(
        **payload.model_dump(),
        snapshot_status="refreshing" if active_task else "missing",
        snapshot_updated_at=None,
        snapshot_task_id=active_task.id if active_task else None,
    )


@router.post("/dashboard/refresh", response_model=DashboardRefreshOut)
async def refresh_dashboard_snapshot(
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(HOME_REFRESH)),
) -> DashboardRefreshOut:
    task_id, existing = await enqueue_task(
        db,
        job_name=REFRESH_DASHBOARD_JOB_NAME,
        trigger_source="manual",
        dedupe_key=REFRESH_DASHBOARD_JOB_NAME,
        payload={"triggered_by": "manual_refresh"},
    )
    return DashboardRefreshOut(task_id=task_id, existing=existing)


@router.get("/prometheus", response_class=PlainTextResponse)
async def prometheus_metrics(
    db: AsyncSession = Depends(db_session_readonly),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(MONITOR_VIEW)),
) -> PlainTextResponse:
    """基础 Prometheus 文本格式指标。"""
    pending = (
        await db.execute(
            select(func.count()).select_from(TaskRun).where(TaskRun.status == "pending")
        )
    ).scalar() or 0

    running = (
        await db.execute(
            select(func.count()).select_from(TaskRun).where(TaskRun.status == "running")
        )
    ).scalar() or 0

    lines = [
        "# HELP restock_taskrun_pending Number of pending tasks",
        "# TYPE restock_taskrun_pending gauge",
        f"restock_taskrun_pending {pending}",
        "# HELP restock_taskrun_running Number of running tasks",
        "# TYPE restock_taskrun_running gauge",
        f"restock_taskrun_running {running}",
        "# HELP restock_up Application is up",
        "# TYPE restock_up gauge",
        "restock_up 1",
    ]
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")
