"""配置管理 API(covers global / sku / warehouse / zipcode / shop)。"""

from typing import Any

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_session
from app.core.exceptions import ConflictError, NotFound, ValidationFailed
from app.core.query import escape_like
from app.models.global_config import GlobalConfig
from app.models.inventory import InventorySnapshotLatest
from app.models.product_listing import ProductListing
from app.models.shop import Shop
from app.models.sku import SkuConfig
from app.models.warehouse import Warehouse
from app.models.zipcode_rule import ZipcodeRule
from app.schemas.config import (
    GlobalConfigOut,
    GlobalConfigPatch,
    ShopOut,
    ShopPatch,
    SkuConfigListOut,
    SkuConfigOut,
    SkuConfigPatch,
    WarehouseCountryPatch,
    WarehouseOut,
    ZipcodeRuleIn,
    ZipcodeRuleOut,
)
from app.tasks.queue import enqueue_task
from app.tasks.scheduler import reload_scheduler

router = APIRouter(prefix="/api/config", tags=["config"])


def _warehouse_total_stock_subquery():
    return (
        select(
            InventorySnapshotLatest.warehouse_id.label("warehouse_id"),
            func.coalesce(
                func.sum(InventorySnapshotLatest.available + InventorySnapshotLatest.reserved),
                0,
            ).label("total_stock"),
        )
        .group_by(InventorySnapshotLatest.warehouse_id)
        .subquery()
    )


def _warehouse_list_stmt():
    stock_subquery = _warehouse_total_stock_subquery()
    return (
        select(
            Warehouse,
            func.coalesce(stock_subquery.c.total_stock, 0).label("total_stock"),
        )
        .outerjoin(stock_subquery, stock_subquery.c.warehouse_id == Warehouse.id)
        .order_by(Warehouse.country, Warehouse.id)
    )


def _warehouse_out_from_row(row) -> WarehouseOut:
    warehouse, total_stock = row
    return WarehouseOut.model_validate(
        {
            "id": warehouse.id,
            "name": warehouse.name,
            "type": warehouse.type,
            "country": warehouse.country,
            "replenish_site_raw": warehouse.replenish_site_raw,
            "total_stock": int(total_stock or 0),
        }
    )


async def init_sku_configs_from_listings(db: AsyncSession) -> int:
    sku_codes = (
        (
            await db.execute(
                select(ProductListing.commodity_sku)
                .distinct()
                .where(ProductListing.commodity_sku.is_not(None))
                .order_by(ProductListing.commodity_sku)
            )
        )
        .scalars()
        .all()
    )
    if not sku_codes:
        return 0

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
            [{"commodity_sku": code, "enabled": True} for code in missing_codes]
        )
    )
    await db.commit()
    return len(missing_codes)


# ============================================================
# Global Config
# ============================================================
@router.get("/global", response_model=GlobalConfigOut)
async def get_global(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> GlobalConfigOut:
    row = (await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))).scalar_one()
    return GlobalConfigOut.model_validate(row)


@router.patch("/global", response_model=GlobalConfigOut)
async def patch_global(
    patch: GlobalConfigPatch,
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> GlobalConfigOut:
    updates = patch.model_dump(exclude_none=True)
    if updates:
        await db.execute(update(GlobalConfig).where(GlobalConfig.id == 1).values(**updates))
        await db.commit()
        if {"sync_interval_minutes", "calc_cron", "scheduler_enabled"} & updates.keys():
            await reload_scheduler()
    row = (await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))).scalar_one()
    return GlobalConfigOut.model_validate(row)


# ============================================================
# SKU Config
# ============================================================
@router.get("/sku", response_model=SkuConfigListOut)
async def list_sku_configs(
    enabled: bool | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> SkuConfigListOut:
    base = select(SkuConfig).order_by(SkuConfig.commodity_sku)
    if enabled is not None:
        base = base.where(SkuConfig.enabled.is_(enabled))
    if keyword:
        base = base.where(SkuConfig.commodity_sku.ilike(f"%{escape_like(keyword)}%", escape="\\"))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (await db.execute(base.offset((page - 1) * page_size).limit(page_size))).scalars().all()

    # 一次性 JOIN product_listing 获取 commodity_name + main_image
    sku_codes = [r.commodity_sku for r in rows]
    name_map: dict[str, tuple[str | None, str | None]] = {}
    if sku_codes:
        listing_rows = (
            await db.execute(
                select(
                    ProductListing.commodity_sku,
                    ProductListing.commodity_name,
                    ProductListing.main_image,
                ).where(ProductListing.commodity_sku.in_(sku_codes))
            )
        ).all()
        for sku, name, img in listing_rows:
            if sku not in name_map:
                name_map[sku] = (name, img)

    items = []
    for r in rows:
        name, img = name_map.get(r.commodity_sku, (None, None))
        items.append(
            SkuConfigOut(
                commodity_sku=r.commodity_sku,
                enabled=r.enabled,
                lead_time_days=r.lead_time_days,
                commodity_name=name,
                main_image=img,
            )
        )
    return SkuConfigListOut(items=items, total=int(total or 0))


@router.post("/sku/init")
async def init_sku_configs(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> dict[str, int]:
    created = await init_sku_configs_from_listings(db)
    total = (await db.execute(select(func.count()).select_from(SkuConfig))).scalar_one()
    return {"created": created, "total": int(total or 0)}


@router.patch("/sku/{commodity_sku}", response_model=SkuConfigOut)
async def patch_sku_config(
    patch: SkuConfigPatch,
    commodity_sku: str = Path(...),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> SkuConfigOut:
    row = (
        await db.execute(select(SkuConfig).where(SkuConfig.commodity_sku == commodity_sku))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(f"SKU {commodity_sku} 未配置")
    updates = patch.model_dump(exclude_unset=True)
    if updates:
        await db.execute(
            update(SkuConfig).where(SkuConfig.commodity_sku == commodity_sku).values(**updates)
        )
        await db.refresh(row)
    return SkuConfigOut.model_validate({**row.__dict__, "commodity_name": None, "main_image": None})


# ============================================================
# Warehouse
# ============================================================
@router.get("/warehouse", response_model=list[WarehouseOut])
async def list_warehouses(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> list[WarehouseOut]:
    rows = (await db.execute(_warehouse_list_stmt())).all()
    return [_warehouse_out_from_row(row) for row in rows]


@router.patch("/warehouse/{warehouse_id}/country", response_model=WarehouseOut)
async def patch_warehouse_country(
    patch: WarehouseCountryPatch,
    warehouse_id: str = Path(...),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> WarehouseOut:
    row = (
        await db.execute(select(Warehouse).where(Warehouse.id == warehouse_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(f"仓库 {warehouse_id} 不存在")
    new_country = patch.country.upper() if patch.country else None
    await db.execute(
        update(Warehouse).where(Warehouse.id == warehouse_id).values(country=new_country)
    )
    # 同步更新 inventory_snapshot_latest 中该仓库的 country，避免等下次库存同步
    await db.execute(
        update(InventorySnapshotLatest)
        .where(InventorySnapshotLatest.warehouse_id == warehouse_id)
        .values(country=new_country)
    )
    await db.commit()
    updated_row = (
        await db.execute(_warehouse_list_stmt().where(Warehouse.id == warehouse_id))
    ).one()
    return _warehouse_out_from_row(updated_row)


# ============================================================
# Zipcode Rule
# ============================================================
@router.get("/zipcode-rules", response_model=list[ZipcodeRuleOut])
async def list_zipcode_rules(
    country: str | None = Query(default=None),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> list[ZipcodeRuleOut]:
    base = select(ZipcodeRule).order_by(ZipcodeRule.country, ZipcodeRule.priority)
    if country:
        base = base.where(ZipcodeRule.country == country.upper())
    rows = (await db.execute(base)).scalars().all()
    return [ZipcodeRuleOut.model_validate(r) for r in rows]


@router.post("/zipcode-rules", response_model=ZipcodeRuleOut, status_code=201)
async def create_zipcode_rule(
    body: ZipcodeRuleIn,
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> ZipcodeRuleOut:
    # 校验仓库存在
    wh = (
        await db.execute(select(Warehouse).where(Warehouse.id == body.warehouse_id))
    ).scalar_one_or_none()
    if wh is None:
        raise NotFound(f"仓库 {body.warehouse_id} 不存在")
    if wh.country != body.country.upper():
        raise ValidationFailed(f"仓库 {body.warehouse_id} 与规则国家 {body.country.upper()} 不匹配")

    rule = ZipcodeRule(
        country=body.country.upper(),
        prefix_length=body.prefix_length,
        value_type=body.value_type,
        operator=body.operator,
        compare_value=body.compare_value,
        warehouse_id=body.warehouse_id,
        priority=body.priority,
    )
    db.add(rule)
    await db.flush()
    return ZipcodeRuleOut.model_validate(rule)


@router.patch("/zipcode-rules/{rule_id}", response_model=ZipcodeRuleOut)
async def patch_zipcode_rule(
    body: ZipcodeRuleIn,
    rule_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> ZipcodeRuleOut:
    rule = (
        await db.execute(select(ZipcodeRule).where(ZipcodeRule.id == rule_id))
    ).scalar_one_or_none()
    if rule is None:
        raise NotFound(f"规则 {rule_id} 不存在")
    wh = (
        await db.execute(select(Warehouse).where(Warehouse.id == body.warehouse_id))
    ).scalar_one_or_none()
    if wh is None:
        raise NotFound(f"仓库 {body.warehouse_id} 不存在")
    if wh.country != body.country.upper():
        raise ValidationFailed(f"仓库 {body.warehouse_id} 与规则国家 {body.country.upper()} 不匹配")
    await db.execute(
        update(ZipcodeRule)
        .where(ZipcodeRule.id == rule_id)
        .values(
            country=body.country.upper(),
            prefix_length=body.prefix_length,
            value_type=body.value_type,
            operator=body.operator,
            compare_value=body.compare_value,
            warehouse_id=body.warehouse_id,
            priority=body.priority,
        )
    )
    await db.refresh(rule)
    return ZipcodeRuleOut.model_validate(rule)


@router.delete("/zipcode-rules/{rule_id}", status_code=204)
async def delete_zipcode_rule(
    rule_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> None:
    res = await db.execute(delete(ZipcodeRule).where(ZipcodeRule.id == rule_id))
    if res.rowcount == 0:
        raise NotFound(f"规则 {rule_id} 不存在")
    return None


# ============================================================
# Shop
# ============================================================
@router.get("/shops", response_model=list[ShopOut])
async def list_shops(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> list[ShopOut]:
    rows = (await db.execute(select(Shop).order_by(Shop.id))).scalars().all()
    return [ShopOut.model_validate(r) for r in rows]


@router.post("/shops/refresh")
async def refresh_shops(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> dict[str, Any]:
    """触发 sync_shop 任务从赛狐刷新店铺列表。"""
    task_id, existing = await enqueue_task(db, job_name="sync_shop", trigger_source="manual")
    return {"task_id": task_id, "existing": existing}


@router.patch("/shops/{shop_id}", response_model=ShopOut)
async def patch_shop(
    patch: ShopPatch,
    shop_id: str = Path(...),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> ShopOut:
    row = (await db.execute(select(Shop).where(Shop.id == shop_id))).scalar_one_or_none()
    if row is None:
        raise NotFound(f"店铺 {shop_id} 不存在")
    if row.status != "0" and patch.sync_enabled:
        raise ConflictError("授权失效的店铺无法启用同步")
    await db.execute(update(Shop).where(Shop.id == shop_id).values(sync_enabled=patch.sync_enabled))
    await db.refresh(row)
    return ShopOut.model_validate(row)
