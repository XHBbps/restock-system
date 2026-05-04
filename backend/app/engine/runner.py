"""Rule-engine orchestration: run steps 1-6 and persist suggestions."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.locks import ENGINE_RUN_ADVISORY_LOCK_KEY
from app.core.logging import get_logger
from app.core.restock_regions import resolve_allowed_restock_regions
from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.engine.step1_velocity import run_step1
from app.engine.step2_sale_days import run_step2
from app.engine.step3_country_qty import compute_country_qty
from app.engine.step4_total import compute_total, load_local_inventory
from app.engine.step5_warehouse_split import (
    explain_country_qty_split,
    load_all_sku_country_orders,
    load_country_warehouses,
    load_zipcode_rules,
)
from app.engine.step6_timing import compute_urgency_for_sku
from app.models.global_config import GlobalConfig
from app.models.sku import SkuConfig
from app.models.suggestion import Suggestion, SuggestionItem
from app.services.physical_item import load_physical_sku_resolver
from app.tasks.jobs import JobContext

logger = get_logger(__name__)


async def run_engine(
    ctx: JobContext,
    *,
    demand_date: date,
    triggered_by: str = "scheduler",
) -> int | None:
    today = now_beijing().date()
    demand_days = max((demand_date - today).days, 0)

    async with async_session_factory() as db:
        await db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": ENGINE_RUN_ADVISORY_LOCK_KEY},
        )
        config = (await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))).scalar_one()

        if not config.suggestion_generation_enabled:
            logger.warning("engine_generation_disabled", triggered_by=triggered_by)
            await ctx.progress(current_step="完成", step_detail="补货建议生成已关闭，跳过本次计算")
            return None

        global_snapshot = _config_snapshot(config, demand_date=demand_date)
        allowed_countries = resolve_allowed_restock_regions(config.restock_regions)

        if config.target_days <= 0:
            raise ValueError(f"GlobalConfig.target_days must be > 0, got {config.target_days}")
        if config.buffer_days < 0:
            raise ValueError(f"GlobalConfig.buffer_days must be >= 0, got {config.buffer_days}")
        if config.lead_time_days < 0:
            raise ValueError(
                f"GlobalConfig.lead_time_days must be >= 0, got {config.lead_time_days}"
            )
        if config.safety_stock_days < 0:
            raise ValueError(
                f"GlobalConfig.safety_stock_days must be >= 0, got {config.safety_stock_days}"
            )
        if config.target_days < config.lead_time_days:
            raise ValueError(
                "GlobalConfig.target_days must be >= GlobalConfig.lead_time_days, "
                f"got target_days={config.target_days}, lead_time_days={config.lead_time_days}"
            )
        effective_target_days = config.target_days + demand_days

        enabled_skus = (
            await db.execute(
                select(SkuConfig.commodity_sku, SkuConfig.lead_time_days).where(
                    SkuConfig.enabled.is_(True)
                )
            )
        ).all()
        resolver = await load_physical_sku_resolver(db)
        sku_list = sorted({row[0] for row in enabled_skus})
        source_sku_list = sku_list
        sku_lead_time: dict[str, int | None] = {}
        for raw_sku, lead_time_days in enabled_skus:
            sku_lead_time[raw_sku] = lead_time_days

        if not sku_list:
            logger.warning("engine_no_enabled_sku", triggered_by=triggered_by)
            await ctx.progress(current_step="完成", step_detail="无启用 SKU，未生成建议单")
            return None

        await ctx.progress(current_step="Step 1: 计算 velocity", total_steps=7)
        # Σvelocity 参与采购量（step4）计算时须覆盖所有国家（含白名单外的动销），
        # 因此这里不按 restock_regions 过滤。白名单只作用于后续的 country_qty。
        velocity = await run_step1(
            db,
            source_sku_list,
            today,
        )

        await ctx.progress(current_step="Step 2: 计算 sale_days")
        sale_days, inventory = await run_step2(
            db,
            velocity,
            source_sku_list,
            sku_to_group_key=resolver.sku_to_group_key,
            members_by_group_key=resolver.members_by_group_key,
        )

        await ctx.progress(current_step="Step 3: 计算各国补货量")
        country_qty_all = compute_country_qty(velocity, inventory, effective_target_days)
        if allowed_countries is not None:
            country_qty = {
                sku: {c: q for c, q in cq.items() if c in allowed_countries}
                for sku, cq in country_qty_all.items()
            }
        else:
            country_qty = country_qty_all

        await ctx.progress(current_step="Step 4: 计算采购量")
        local_stock = await load_local_inventory(
            db,
            source_sku_list,
            velocity,
            sku_to_group_key=resolver.sku_to_group_key,
            members_by_group_key=resolver.members_by_group_key,
        )

        await ctx.progress(current_step="Step 5: 计算分仓")
        country_warehouses = await load_country_warehouses(db)
        zipcode_rules = await load_zipcode_rules(db)
        all_orders = await load_all_sku_country_orders(
            db,
            source_sku_list,
            today,
            allowed_countries=allowed_countries,
        )

        items_to_insert: list[dict[str, Any]] = []
        for sku in sku_list:
            sku_country_qty = country_qty.get(sku, {})
            restock_total = sum(sku_country_qty.values())
            purchase_qty = compute_total(
                sku=sku,
                country_qty_for_sku=sku_country_qty,
                velocity_for_sku=velocity.get(sku, {}),
                local_stock_for_sku=local_stock.get(sku),
                buffer_days=config.buffer_days,
                safety_stock_days=config.safety_stock_days,
            )

            if purchase_qty <= 0 and restock_total <= 0:
                continue

            warehouse_breakdown: dict[str, dict[str, int]] = {}
            allocation_snapshot: dict[str, dict[str, Any]] = {}
            for country, qty in sku_country_qty.items():
                if qty <= 0:
                    continue
                orders = all_orders.get((sku, country), [])
                allocation = explain_country_qty_split(
                    sku=sku,
                    country=country,
                    country_qty=qty,
                    orders=orders,
                    rules=zipcode_rules,
                    country_warehouses=country_warehouses.get(country, []),
                )
                allocation_snapshot[country] = {
                    "allocation_mode": allocation.allocation_mode,
                    "matched_order_qty": allocation.matched_order_qty,
                    "unknown_order_qty": allocation.unknown_order_qty,
                    "eligible_warehouses": allocation.eligible_warehouses,
                }
                if allocation.warehouse_breakdown:
                    warehouse_breakdown[country] = allocation.warehouse_breakdown

            lead_time = sku_lead_time.get(sku) or config.lead_time_days
            timing = compute_urgency_for_sku(
                sale_days_for_sku=sale_days.get(sku, {}),
                country_qty_for_sku=sku_country_qty,
                lead_time_days=lead_time,
                today=today,
            )

            items_to_insert.append(
                {
                    "commodity_sku": sku,
                    "total_qty": restock_total,
                    "country_breakdown": sku_country_qty,
                    "warehouse_breakdown": warehouse_breakdown,
                    "allocation_snapshot": allocation_snapshot,
                    "velocity_snapshot": velocity.get(sku, {}),
                    "sale_days_snapshot": sale_days.get(sku, {}),
                    "urgent": timing.urgent,
                    "purchase_qty": purchase_qty,
                    "restock_dates": timing.restock_dates or {},
                }
            )

        if not items_to_insert:
            await ctx.progress(current_step="完成", step_detail="no_suggestion_needed")
            return None

        await ctx.progress(current_step="Step 6: 持久化建议单")
        await _archive_active(db)
        suggestion_id = await _persist_suggestion(
            db,
            global_snapshot=global_snapshot,
            triggered_by=triggered_by,
            items=items_to_insert,
        )

        await ctx.progress(current_step="完成", step_detail=f"建议单 id = {suggestion_id}")
        return suggestion_id


def _config_snapshot(config: GlobalConfig, *, demand_date: date | None = None) -> dict[str, Any]:
    snapshot = {
        "buffer_days": config.buffer_days,
        "target_days": config.target_days,
        "lead_time_days": config.lead_time_days,
        "safety_stock_days": config.safety_stock_days,
        "restock_regions": list(config.restock_regions or []),
        "eu_countries": list(config.eu_countries or []),
        "shop_sync_mode": config.shop_sync_mode,
        "snapshot_at": now_beijing().isoformat(),
    }
    if demand_date is not None:
        snapshot["demand_date"] = demand_date.isoformat()
    return snapshot


async def _persist_suggestion(
    db: AsyncSession,
    global_snapshot: dict[str, Any],
    triggered_by: str,
    items: list[dict[str, Any]],
) -> int:
    procurement_item_count = sum(1 for item in items if int(item.get("purchase_qty", 0) or 0) > 0)
    restock_item_count = sum(1 for item in items if int(item.get("total_qty", 0) or 0) > 0)
    result = await db.execute(
        insert(Suggestion)
        .values(
            status="draft",
            global_config_snapshot=global_snapshot,
            triggered_by=triggered_by,
            total_items=len(items),
            procurement_item_count=procurement_item_count,
            restock_item_count=restock_item_count,
        )
        .returning(Suggestion.id)
    )
    suggestion_id = result.scalar_one()
    if items:
        for item in items:
            item["suggestion_id"] = suggestion_id
        await db.execute(insert(SuggestionItem).values(items))
    await db.commit()
    return suggestion_id


async def _archive_active(db: AsyncSession) -> None:
    await db.execute(
        update(Suggestion)
        .where(Suggestion.status == "draft")
        .values(status="archived", archived_at=now_beijing())
    )
