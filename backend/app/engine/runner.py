"""Rule-engine orchestration: run steps 1-6 and persist suggestions."""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from sqlalchemy import insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.countries import is_reportable_country_code
from app.core.locks import ENGINE_RUN_ADVISORY_LOCK_KEY
from app.core.logging import get_logger
from app.core.restock_regions import resolve_allowed_restock_regions
from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.engine.restock_dates import demand_restock_dates
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
from app.engine.warnings import build_calculation_warnings
from app.models.global_config import GlobalConfig
from app.models.sku import SkuConfig
from app.models.suggestion import Suggestion, SuggestionItem
from app.services.physical_item import load_physical_sku_resolver
from app.tasks.jobs import JobContext

logger = get_logger(__name__)


def _filter_reportable_country_map(
    values_by_sku: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        sku: {
            country: value
            for country, value in country_map.items()
            if is_reportable_country_code(country)
        }
        for sku, country_map in values_by_sku.items()
    }


def _filter_allowed_country_map(
    values_by_sku: dict[str, dict[str, Any]],
    allowed_countries: set[str] | None,
) -> dict[str, dict[str, Any]]:
    reportable = _filter_reportable_country_map(values_by_sku)
    if allowed_countries is None:
        return reportable
    return {
        sku: {country: value for country, value in country_map.items() if country in allowed_countries}
        for sku, country_map in reportable.items()
    }


def _build_calculation_inputs_snapshot(
    *,
    generated_at: str,
    demand_date: date,
    target_days: int,
    demand_days: int,
    effective_target_days: int,
    safety_stock_days: int,
    country_qty_for_sku: dict[str, int],
    velocity_for_sku: dict[str, float],
    inventory_for_sku: dict[str, Any],
    local_stock_for_sku: Any | None,
    sale_days_for_sku: dict[str, float],
    restock_dates_for_sku: dict[str, str | None],
    purchase_qty: int,
) -> dict[str, Any]:
    country_restock_total = int(sum(int(qty or 0) for qty in country_qty_for_sku.values()))
    velocity_total = float(sum(float(value or 0) for value in velocity_for_sku.values()))
    safety_stock_qty = math.ceil(velocity_total * safety_stock_days)
    local_available = int(getattr(local_stock_for_sku, "available", 0) or 0)
    local_reserved = int(getattr(local_stock_for_sku, "reserved", 0) or 0)
    local_total = local_available + local_reserved
    raw_purchase_qty = country_restock_total - local_total + safety_stock_qty

    restock_countries: dict[str, dict[str, Any]] = {}
    for country, final_qty in sorted(country_qty_for_sku.items()):
        final_restock_qty = int(final_qty or 0)
        if final_restock_qty <= 0:
            continue
        daily_velocity = float(velocity_for_sku.get(country, 0) or 0)
        stock = inventory_for_sku.get(country)
        overseas_available = int(getattr(stock, "available", 0) or 0)
        overseas_reserved = int(getattr(stock, "reserved", 0) or 0)
        in_transit = int(getattr(stock, "in_transit", 0) or 0)
        overseas_total = overseas_available + overseas_reserved + in_transit
        target_stock_qty = math.ceil(effective_target_days * daily_velocity)
        raw_restock_qty = target_stock_qty - overseas_total
        sale_days = sale_days_for_sku.get(country)
        restock_countries[country] = {
            "effective_target_days": effective_target_days,
            "daily_velocity": daily_velocity,
            "overseas_available": overseas_available,
            "overseas_reserved": overseas_reserved,
            "in_transit": in_transit,
            "overseas_stock_total": overseas_total,
            "target_stock_qty": target_stock_qty,
            "raw_restock_qty": raw_restock_qty,
            "final_restock_qty": final_restock_qty,
            "sale_days": float(sale_days) if sale_days is not None else None,
            "restock_date": restock_dates_for_sku.get(country),
        }

    return {
        "version": 1,
        "generated_at": generated_at,
        "demand_date": demand_date.isoformat(),
        "target_days": target_days,
        "demand_days": demand_days,
        "effective_target_days": effective_target_days,
        "safety_stock_days": safety_stock_days,
        "purchase": {
            "country_restock_qty_total": country_restock_total,
            "country_restock_qty_by_country": {
                country: int(qty or 0) for country, qty in sorted(country_qty_for_sku.items())
            },
            "daily_velocity_total": velocity_total,
            "daily_velocity_by_country": {
                country: float(value or 0) for country, value in sorted(velocity_for_sku.items())
            },
            "safety_stock_qty": safety_stock_qty,
            "local_stock_available": local_available,
            "local_stock_reserved": local_reserved,
            "local_stock_total": local_total,
            "raw_purchase_qty": raw_purchase_qty,
            "final_purchase_qty": int(purchase_qty or 0),
        },
        "restock": {
            "countries": restock_countries,
        },
    }


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
        if config.lead_time_days is None or config.lead_time_days < 0:
            raise ValueError(
                f"GlobalConfig.lead_time_days must be >= 0, got {config.lead_time_days}"
            )
        global_lead_time_days = config.lead_time_days
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
        velocity = _filter_reportable_country_map(
            await run_step1(
                db,
                source_sku_list,
                today,
            )
        )

        await ctx.progress(current_step="Step 2: 计算 sale_days")
        sale_days, inventory = await run_step2(
            db,
            velocity,
            source_sku_list,
            sku_to_group_key=resolver.sku_to_group_key,
            members_by_group_key=resolver.members_by_group_key,
        )
        sale_days = _filter_reportable_country_map(sale_days)
        inventory = _filter_reportable_country_map(inventory)

        await ctx.progress(current_step="Step 3: 计算各国补货量")
        country_qty_all = compute_country_qty(velocity, inventory, effective_target_days)
        country_qty = _filter_allowed_country_map(country_qty_all, allowed_countries)
        missing_inventory_by_sku = _missing_inventory_countries_by_sku(
            velocity,
            inventory,
            allowed_countries=allowed_countries,
        )

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
        generated_at = now_beijing().isoformat()
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

            sku_specific_lead_time = sku_lead_time.get(sku)
            lead_time = (
                sku_specific_lead_time
                if sku_specific_lead_time is not None
                else global_lead_time_days
            )
            timing = compute_urgency_for_sku(
                sale_days_for_sku=sale_days.get(sku, {}),
                country_qty_for_sku=sku_country_qty,
                lead_time_days=lead_time,
                today=today,
            )
            restock_dates = demand_restock_dates(sku_country_qty, demand_date)
            calculation_warnings = build_calculation_warnings(
                country_qty_for_sku=sku_country_qty,
                sale_days_for_sku=sale_days.get(sku, {}),
                velocity_for_sku=velocity.get(sku, {}),
                missing_inventory_countries=missing_inventory_by_sku.get(sku, set()),
            )
            calculation_inputs_snapshot = _build_calculation_inputs_snapshot(
                generated_at=generated_at,
                demand_date=demand_date,
                target_days=config.target_days,
                demand_days=demand_days,
                effective_target_days=effective_target_days,
                safety_stock_days=config.safety_stock_days,
                country_qty_for_sku=sku_country_qty,
                velocity_for_sku=velocity.get(sku, {}),
                inventory_for_sku=inventory.get(sku, {}),
                local_stock_for_sku=local_stock.get(sku),
                sale_days_for_sku=sale_days.get(sku, {}),
                restock_dates_for_sku=restock_dates,
                purchase_qty=purchase_qty,
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
                    "calculation_warnings": calculation_warnings,
                    "calculation_inputs_snapshot": calculation_inputs_snapshot,
                    "urgent": timing.urgent,
                    "purchase_qty": purchase_qty,
                    "restock_dates": restock_dates,
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


def _missing_inventory_countries_by_sku(
    velocity: dict[str, dict[str, float]],
    inventory: dict[str, dict[str, Any]],
    *,
    allowed_countries: set[str] | None,
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for sku, country_map in velocity.items():
        for country, daily_rate in country_map.items():
            if daily_rate <= 0:
                continue
            if not is_reportable_country_code(country):
                continue
            if allowed_countries is not None and country not in allowed_countries:
                continue
            if country in inventory.get(sku, {}):
                continue
            result.setdefault(sku, set()).add(country)
    return result


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
