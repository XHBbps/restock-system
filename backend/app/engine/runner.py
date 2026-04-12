"""规则引擎编排器:编排 Step 1-6 + 写入 suggestion 表。

工作流:
1. 读取 sku_config (enabled=true)
2. 加载 product_listing 建立 commodity_sku -> commodity_id 映射
3. 加载 sku_config 的 lead_time 覆盖
4. Step 1: 算 velocity
5. Step 2: 加载库存 + 在途,算 sale_days
6. Step 3: 算 country_qty
7. Step 4: 算 total
8. Step 5: 加载邮编规则 + 国家仓库表,对每个 SKU 每个国家分配仓
9. Step 6: 算 timing
10. 预检 push_blocker(commodity_id 缺失)
11. 写 suggestion + suggestion_item
12. 归档已存在的 draft/partial suggestion
"""

from typing import Any

from sqlalchemy import insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
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
from app.engine.step6_timing import compute_timing_for_sku
from app.models.global_config import GlobalConfig
from app.models.product_listing import ProductListing
from app.models.sku import SkuConfig
from app.models.suggestion import Suggestion, SuggestionItem
from app.tasks.jobs import JobContext

logger = get_logger(__name__)

# PostgreSQL transaction-level advisory lock key: prevents concurrent engine
# runs from overwriting each other. Any stable int32 unique vs other locks.
ENGINE_RUN_ADVISORY_LOCK_KEY = 7429001


async def run_engine(ctx: JobContext, *, triggered_by: str = "scheduler") -> int | None:
    """执行一次完整的规则引擎,返回新建 suggestion id。"""
    today = now_beijing().date()

    async with async_session_factory() as db:
        # M-N5: transaction-level advisory lock blocks concurrent engine runs
        # to prevent them from overwriting each other's suggestion. Released
        # automatically when the transaction ends.
        await db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": ENGINE_RUN_ADVISORY_LOCK_KEY},
        )
        # 加载全局配置
        config = (await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))).scalar_one()
        global_snapshot = _config_snapshot(config)

        # P1-1: 配置正值校验,防止静默产出错误结果
        if config.target_days <= 0:
            raise ValueError(f"GlobalConfig.target_days must be > 0, got {config.target_days}")
        if config.buffer_days < 0:
            raise ValueError(f"GlobalConfig.buffer_days must be >= 0, got {config.buffer_days}")
        if config.lead_time_days < 0:
            raise ValueError(f"GlobalConfig.lead_time_days must be >= 0, got {config.lead_time_days}")

        # 加载启用 SKU
        enabled_skus = (
            await db.execute(
                select(SkuConfig.commodity_sku, SkuConfig.lead_time_days).where(
                    SkuConfig.enabled.is_(True)
                )
            )
        ).all()
        sku_list = [r[0] for r in enabled_skus]
        sku_lead_time: dict[str, int | None] = {r[0]: r[1] for r in enabled_skus}

        if not sku_list:
            logger.warning(
                "engine_no_enabled_sku",
                extra={"triggered_by": triggered_by},
            )
            await ctx.progress(
                current_step="完成",
                step_detail="无启用 SKU,跳过本次计算",
            )
            return None

        await ctx.progress(
            current_step="Step 1: 计算 velocity",
            step_detail=f"启用 SKU 数 {len(sku_list)}",
            total_steps=7,
        )
        velocity = await run_step1(db, sku_list, today)

        await ctx.progress(current_step="Step 2: 计算 sale_days")
        sale_days, inventory = await run_step2(db, velocity, sku_list)

        await ctx.progress(current_step="Step 3: 各国补货量")
        country_qty = compute_country_qty(velocity, inventory, config.target_days)

        await ctx.progress(current_step="Step 4: 总采购量")
        local_stock = await load_local_inventory(db, sku_list)

        await ctx.progress(current_step="Step 5: 仓内分配")
        country_warehouses = await load_country_warehouses(db)
        zipcode_rules = await load_zipcode_rules(db)

        # * 一次性批量加载所有 SKU 近 30 天订单,避免 N+1(宪法 V)
        all_orders = await load_all_sku_country_orders(db, sku_list, today)

        # 加载 commodity_id 映射(取每个 sku 任一 listing 的 commodity_id)
        commodity_id_map = await _load_commodity_id_map(db, sku_list)

        # 对每个 SKU 计算最终结果
        items_to_insert: list[dict[str, Any]] = []
        processed = 0
        for sku in sku_list:
            sku_country_qty = country_qty.get(sku, {})
            if not sku_country_qty:
                # 该 SKU 全球无补货建议,跳过
                continue

            total_qty = compute_total(
                sku=sku,
                country_qty_for_sku=sku_country_qty,
                velocity_for_sku=velocity.get(sku, {}),
                local_stock_for_sku=local_stock.get(sku),
                buffer_days=config.buffer_days,
            )
            if total_qty <= 0:
                continue

            # 仓内分配(订单已批量加载,内存查表,无 DB 访问)
            warehouse_breakdown: dict[str, dict[str, int]] = {}
            allocation_snapshot: dict[str, dict[str, Any]] = {}
            for country, q in sku_country_qty.items():
                if q <= 0:
                    continue
                orders = all_orders.get((sku, country), [])
                allocation = explain_country_qty_split(
                    sku=sku,
                    country=country,
                    country_qty=q,
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

            # Timing
            lead_time = sku_lead_time.get(sku) or config.lead_time_days
            timing = compute_timing_for_sku(
                sale_days_for_sku=sale_days.get(sku, {}),
                country_qty_for_sku=sku_country_qty,
                target_days=config.target_days,
                lead_time_days=lead_time,
                today=today,
            )

            # push_blocker 预检
            commodity_id = commodity_id_map.get(sku)
            push_blocker = None if commodity_id else "missing_commodity_id"
            push_status = "blocked" if push_blocker else "pending"

            items_to_insert.append(
                {
                    "commodity_sku": sku,
                    "commodity_id": commodity_id,
                    "total_qty": total_qty,
                    "country_breakdown": sku_country_qty,
                    "warehouse_breakdown": warehouse_breakdown,
                    "allocation_snapshot": allocation_snapshot,
                    "t_purchase": {c: d.isoformat() for c, d in timing.t_purchase.items()},
                    "t_ship": {c: d.isoformat() for c, d in timing.t_ship.items()},
                    "velocity_snapshot": velocity.get(sku, {}),
                    "sale_days_snapshot": sale_days.get(sku, {}),
                    "urgent": timing.urgent,
                    "push_blocker": push_blocker,
                    "push_status": push_status,
                }
            )

            processed += 1
            if processed % 20 == 0:
                await ctx.progress(step_detail=f"已处理 {processed} 条建议")

        await ctx.progress(current_step="Step 6: 持久化建议单")
        suggestion_id = await _persist_suggestion(
            db, global_snapshot, triggered_by, items_to_insert
        )

        await ctx.progress(
            current_step="完成",
            step_detail=f"生成 {len(items_to_insert)} 条建议",
        )
        return suggestion_id


def _config_snapshot(config: GlobalConfig) -> dict[str, Any]:
    return {
        "buffer_days": config.buffer_days,
        "target_days": config.target_days,
        "lead_time_days": config.lead_time_days,
        "include_tax": config.include_tax,
        "default_purchase_warehouse_id": config.default_purchase_warehouse_id,
        "shop_sync_mode": config.shop_sync_mode,
        "snapshot_at": now_beijing().isoformat(),
    }


async def _load_commodity_id_map(db: AsyncSession, skus: list[str]) -> dict[str, str | None]:
    """每个 commodity_sku 取任意一个 commodity_id。"""
    rows = (
        await db.execute(
            select(ProductListing.commodity_sku, ProductListing.commodity_id)
            .where(ProductListing.commodity_sku.in_(skus))
            .where(ProductListing.commodity_id.is_not(None))
            .order_by(ProductListing.commodity_sku, ProductListing.commodity_id)
        )
    ).all()
    result: dict[str, str | None] = dict.fromkeys(skus)
    for sku, cid in rows:
        if result.get(sku) is None and cid:
            result[sku] = cid
    return result


async def _persist_suggestion(
    db: AsyncSession,
    global_snapshot: dict[str, Any],
    triggered_by: str,
    items: list[dict[str, Any]],
) -> int:
    await _archive_active(db)
    sug = await db.execute(
        insert(Suggestion)
        .values(
            status="draft",
            global_config_snapshot=global_snapshot,
            triggered_by=triggered_by,
            total_items=len(items),
        )
        .returning(Suggestion.id)
    )
    suggestion_id = sug.scalar_one()
    if items:
        for it in items:
            it["suggestion_id"] = suggestion_id
        await db.execute(insert(SuggestionItem).values(items))
    await db.commit()
    return suggestion_id


async def _archive_active(db: AsyncSession) -> None:
    """归档现有 draft / partial 建议单。"""
    await db.execute(
        update(Suggestion)
        .where(Suggestion.status.in_(("draft", "partial")))
        .values(status="archived", archived_at=now_beijing())
    )
