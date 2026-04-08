"""规则引擎编排器：编排 Step 1–6 + 写入 suggestion 表。

工作流：
1. 读取 sku_config (enabled=true)
2. 加载 product_listing 建立 commodity_sku → commodity_id 映射
3. 加载 sku_config 的 lead_time 覆盖
4. Step 1: 算 velocity
5. Step 2: 加载库存 + 在途，算 sale_days
6. Step 3: 算 country_qty + overstock
7. Step 4: 算 total
8. Step 5: 加载邮编规则 + 国家仓库表，对每个 SKU 每个国家分配仓
9. Step 6: 算 timing
10. 预检 push_blocker（commodity_id 缺失）
11. 写 suggestion + suggestion_item
12. 归档已存在的 draft/partial suggestion
"""

from datetime import date
from typing import Any

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.engine.step1_velocity import run_step1
from app.engine.step2_sale_days import run_step2
from app.engine.step3_country_qty import compute_country_qty
from app.engine.step4_total import compute_total, load_local_inventory
from app.engine.step5_warehouse_split import (
    load_country_warehouses,
    load_sku_country_orders,
    load_zipcode_rules,
    split_country_qty,
)
from app.engine.step6_timing import compute_timing_for_sku
from app.models.global_config import GlobalConfig
from app.models.inventory import InventorySnapshotLatest
from app.models.order import OrderHeader, OrderItem
from app.models.overstock import OverstockSkuMark
from app.models.product_listing import ProductListing
from app.models.sku import SkuConfig
from app.models.suggestion import Suggestion, SuggestionItem
from app.tasks.jobs import JobContext

logger = get_logger(__name__)


async def run_engine(ctx: JobContext, *, triggered_by: str = "scheduler") -> int:
    """执行一次完整的规则引擎，返回新建 suggestion id。"""
    today = now_beijing().date()

    async with async_session_factory() as db:
        # 加载全局配置
        config = (
            await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
        ).scalar_one()
        global_snapshot = _config_snapshot(config)

        # 加载启用 SKU
        enabled_skus = (
            (
                await db.execute(
                    select(SkuConfig.commodity_sku, SkuConfig.lead_time_days).where(
                        SkuConfig.enabled.is_(True)
                    )
                )
            )
            .all()
        )
        sku_list = [r[0] for r in enabled_skus]
        sku_lead_time: dict[str, int | None] = {r[0]: r[1] for r in enabled_skus}

        if not sku_list:
            logger.warning("engine_no_enabled_sku")
            return await _persist_empty_suggestion(db, global_snapshot, triggered_by)

        await ctx.progress(
            current_step="Step 1: 计算 velocity",
            step_detail=f"启用 SKU 数 {len(sku_list)}",
            total_steps=7,
        )
        velocity = await run_step1(db, sku_list, today)

        await ctx.progress(current_step="Step 2: 计算 sale_days")
        sale_days, inventory = await run_step2(db, velocity, sku_list)

        # FR-032 / US5：刷新积压 SKU 提示表
        await _refresh_overstock_marks(db, velocity, inventory, today)

        await ctx.progress(current_step="Step 3: 各国补货量")
        country_qty, overstock_countries = compute_country_qty(
            velocity, inventory, config.target_days
        )

        await ctx.progress(current_step="Step 4: 总采购量")
        local_stock = await load_local_inventory(db, sku_list)

        await ctx.progress(current_step="Step 5: 仓内分配")
        country_warehouses = await load_country_warehouses(db)
        zipcode_rules = await load_zipcode_rules(db)

        # 加载 commodity_id 映射（取每个 sku 任一 listing 的 commodity_id）
        commodity_id_map = await _load_commodity_id_map(db, sku_list)

        # 对每个 SKU 计算最终结果
        items_to_insert: list[dict[str, Any]] = []
        processed = 0
        for sku in sku_list:
            sku_country_qty = country_qty.get(sku, {})
            if not sku_country_qty:
                # 该 SKU 全球无补货建议，跳过
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

            # 仓内分配（每个国家独立调用）
            warehouse_breakdown: dict[str, dict[str, int]] = {}
            for country, q in sku_country_qty.items():
                if q <= 0:
                    continue
                orders = await load_sku_country_orders(db, sku, country, today)
                breakdown = split_country_qty(
                    sku=sku,
                    country=country,
                    country_qty=q,
                    orders=orders,
                    rules=zipcode_rules,
                    country_warehouses=country_warehouses.get(country, []),
                )
                if breakdown:
                    warehouse_breakdown[country] = breakdown

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
                    "t_purchase": {c: d.isoformat() for c, d in timing.t_purchase.items()},
                    "t_ship": {c: d.isoformat() for c, d in timing.t_ship.items()},
                    "overstock_countries": overstock_countries.get(sku, []),
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


async def _load_commodity_id_map(
    db: AsyncSession, skus: list[str]
) -> dict[str, str | None]:
    """每个 commodity_sku 取任意一个 commodity_id。"""
    rows = (
        await db.execute(
            select(ProductListing.commodity_sku, ProductListing.commodity_id).where(
                ProductListing.commodity_sku.in_(skus)
            )
        )
    ).all()
    result: dict[str, str | None] = {sku: None for sku in skus}
    for sku, cid in rows:
        if result.get(sku) is None and cid:
            result[sku] = cid
    return result


async def _persist_empty_suggestion(
    db: AsyncSession,
    global_snapshot: dict[str, Any],
    triggered_by: str,
) -> int:
    await _archive_active(db)
    sug = await db.execute(
        insert(Suggestion)
        .values(
            status="draft",
            global_config_snapshot=global_snapshot,
            triggered_by=triggered_by,
            total_items=0,
        )
        .returning(Suggestion.id)
    )
    sid = sug.scalar_one()
    await db.commit()
    return sid


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


async def _refresh_overstock_marks(
    db: AsyncSession,
    velocity: dict[str, dict[str, float]],
    inventory: dict[str, dict[str, dict[str, int]]],
    today: date,
) -> None:
    """对所有"全球 velocity 全为 0 且任一仓库存 > 0"的 SKU 维护积压标记。

    UPSERT 语义：保留已有的 processed_at，避免重置用户操作。
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    # 1. 找出所有 全球 velocity 全为 0 的 sku
    overstock_skus: set[str] = set()
    all_skus_with_inventory = set(inventory.keys())
    for sku in all_skus_with_inventory:
        v_map = velocity.get(sku, {})
        if not v_map or all(v == 0 for v in v_map.values()):
            overstock_skus.add(sku)

    if not overstock_skus:
        return

    # 2. 对这些 sku 查 inventory_snapshot_latest 找 available > 0 的仓
    rows = (
        await db.execute(
            select(
                InventorySnapshotLatest.commodity_sku,
                InventorySnapshotLatest.country,
                InventorySnapshotLatest.warehouse_id,
                InventorySnapshotLatest.available,
            )
            .where(InventorySnapshotLatest.commodity_sku.in_(overstock_skus))
            .where(InventorySnapshotLatest.available > 0)
            .where(InventorySnapshotLatest.country.is_not(None))
        )
    ).all()
    if not rows:
        return

    # 3. 批量计算 last_sale_date（最近一次该 SKU 任意国家的 shipped > 0 订单日期）
    last_sale_rows = (
        await db.execute(
            select(
                OrderItem.commodity_sku,
                func.max(OrderHeader.purchase_date).label("last_sale"),
            )
            .join(OrderHeader, OrderHeader.id == OrderItem.order_id)
            .where(OrderItem.commodity_sku.in_(overstock_skus))
            .where(OrderItem.quantity_shipped > 0)
            .where(OrderHeader.order_status.in_(("Shipped", "PartiallyShipped")))
            .group_by(OrderItem.commodity_sku)
        )
    ).all()
    last_sale_map: dict[str, date] = {
        sku: last_dt.date() for sku, last_dt in last_sale_rows if last_dt
    }

    # 4. UPSERT
    for sku, country, warehouse_id, available in rows:
        values = {
            "commodity_sku": sku,
            "country": country,
            "warehouse_id": warehouse_id,
            "current_stock": int(available or 0),
            "last_sale_date": last_sale_map.get(sku),
        }
        stmt = pg_insert(OverstockSkuMark).values(**values)
        # 不覆盖 processed_at（用户手动状态）
        stmt = stmt.on_conflict_do_update(
            constraint="uq_overstock_sku_mark_key",
            set_={
                "current_stock": values["current_stock"],
                "last_sale_date": values["last_sale_date"],
            },
        )
        await db.execute(stmt)
    await db.commit()


async def _archive_active(db: AsyncSession) -> None:
    """归档现有 draft / partial 建议单。"""
    await db.execute(
        update(Suggestion)
        .where(Suggestion.status.in_(("draft", "partial")))
        .values(status="archived", archived_at=now_beijing())
    )
