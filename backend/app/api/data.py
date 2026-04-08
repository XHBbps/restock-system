"""外部数据源观测 API。

READ-ONLY。所有端点从本地同步落库的表查询，返回与赛狐接口
基本一致的 camelCase 结构，供采购员排查"同步进来的数据是否正确"。

覆盖的 7 个资源：
- 订单列表 + 订单详情（order_header / order_item / order_detail）
- 库存明细（inventory_snapshot_latest JOIN warehouse）
- 其他出库（in_transit_record + in_transit_item）
- 仓库列表（warehouse）
- 店铺列表（shop）
- 在线产品信息（product_listing）
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, get_current_session
from app.core.exceptions import NotFound
from app.core.timezone import BEIJING
from app.models.in_transit import InTransitItem, InTransitRecord
from app.models.inventory import InventorySnapshotLatest
from app.models.order import OrderDetail, OrderHeader, OrderItem
from app.models.product_listing import ProductListing
from app.models.shop import Shop
from app.models.warehouse import Warehouse
from app.schemas.data import (
    DataInventoryItem,
    DataInventoryListOut,
    DataOrderDetail,
    DataOrderItem,
    DataOrderListOut,
    DataOrderSummary,
    DataOutRecord,
    DataOutRecordItem,
    DataOutRecordListOut,
    DataProductListing,
    DataProductListingListOut,
    DataShop,
    DataShopListOut,
    DataWarehouse,
    DataWarehouseListOut,
)

router = APIRouter(prefix="/api/data", tags=["data"])


# ============================================================
# 1. 订单列表 + 详情
# ============================================================
@router.get("/orders", response_model=DataOrderListOut)
async def list_orders(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    country: str | None = Query(default=None),
    status: str | None = Query(default=None),
    sku: str | None = Query(default=None, description="按 commodity_sku 或 amazon_order_id 模糊匹配"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> DataOrderListOut:
    base = select(OrderHeader).order_by(OrderHeader.purchase_date.desc())

    if date_from:
        base = base.where(
            OrderHeader.purchase_date >= datetime.combine(date_from, datetime.min.time(), tzinfo=BEIJING)
        )
    if date_to:
        base = base.where(
            OrderHeader.purchase_date
            < datetime.combine(date_to + timedelta(days=1), datetime.min.time(), tzinfo=BEIJING)
        )
    if country:
        base = base.where(OrderHeader.country_code == country.upper())
    if status:
        base = base.where(OrderHeader.order_status == status)
    if sku:
        # 在 amazon_order_id 或通过 order_item JOIN 匹配 commodity_sku
        subq = (
            select(OrderItem.order_id)
            .where(OrderItem.commodity_sku.ilike(f"%{sku}%"))
            .subquery()
        )
        base = base.where(
            (OrderHeader.amazon_order_id.ilike(f"%{sku}%")) | (OrderHeader.id.in_(select(subq.c.order_id)))
        )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        (await db.execute(base.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    )

    # 批量加载 items 与 detail 标志
    order_ids = [r.id for r in rows]
    item_count_map: dict[int, int] = {}
    if order_ids:
        cnt_rows = (
            await db.execute(
                select(OrderItem.order_id, func.count())
                .where(OrderItem.order_id.in_(order_ids))
                .group_by(OrderItem.order_id)
            )
        ).all()
        item_count_map = {oid: int(c) for oid, c in cnt_rows}

    detail_set: set[tuple[str, str]] = set()
    if rows:
        keys = [(r.shop_id, r.amazon_order_id) for r in rows]
        det_rows = (
            await db.execute(
                select(OrderDetail.shop_id, OrderDetail.amazon_order_id).where(
                    OrderDetail.shop_id.in_([k[0] for k in keys])
                )
            )
        ).all()
        detail_set = {(s, a) for s, a in det_rows}

    items = [
        DataOrderSummary(
            shopId=r.shop_id,
            amazonOrderId=r.amazon_order_id,
            marketplaceId=r.marketplace_id,
            countryCode=r.country_code,
            orderStatus=r.order_status,
            orderTotalCurrency=r.order_total_currency,
            orderTotalAmount=r.order_total_amount,
            fulfillmentChannel=r.fulfillment_channel,
            purchaseDate=r.purchase_date,
            lastUpdateDate=r.last_update_date,
            refundStatus=r.refund_status,
            lastSyncAt=r.last_sync_at,
            hasDetail=(r.shop_id, r.amazon_order_id) in detail_set,
            itemCount=item_count_map.get(r.id, 0),
        )
        for r in rows
    ]
    return DataOrderListOut(items=items, total=int(total or 0), page=page, pageSize=page_size)


@router.get("/orders/{shop_id}/{amazon_order_id}", response_model=DataOrderDetail)
async def get_order_detail(
    shop_id: str = Path(...),
    amazon_order_id: str = Path(...),
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> DataOrderDetail:
    header = (
        await db.execute(
            select(OrderHeader).where(
                (OrderHeader.shop_id == shop_id)
                & (OrderHeader.amazon_order_id == amazon_order_id)
            )
        )
    ).scalar_one_or_none()
    if header is None:
        raise NotFound(f"订单 {shop_id}/{amazon_order_id} 不存在")

    item_rows = (
        (await db.execute(select(OrderItem).where(OrderItem.order_id == header.id)))
        .scalars()
        .all()
    )

    detail = (
        await db.execute(
            select(OrderDetail).where(
                (OrderDetail.shop_id == shop_id) & (OrderDetail.amazon_order_id == amazon_order_id)
            )
        )
    ).scalar_one_or_none()

    return DataOrderDetail(
        shopId=header.shop_id,
        amazonOrderId=header.amazon_order_id,
        marketplaceId=header.marketplace_id,
        countryCode=header.country_code,
        orderStatus=header.order_status,
        orderTotalCurrency=header.order_total_currency,
        orderTotalAmount=header.order_total_amount,
        fulfillmentChannel=header.fulfillment_channel,
        purchaseDate=header.purchase_date,
        lastUpdateDate=header.last_update_date,
        refundStatus=header.refund_status,
        isBuyerRequestedCancel=header.is_buyer_requested_cancel,
        lastSyncAt=header.last_sync_at,
        items=[
            DataOrderItem(
                orderItemId=it.order_item_id,
                commoditySku=it.commodity_sku,
                sellerSku=it.seller_sku,
                quantityOrdered=it.quantity_ordered,
                quantityShipped=it.quantity_shipped,
                quantityUnfulfillable=it.quantity_unfulfillable,
                refundNum=it.refund_num,
                itemPriceCurrency=it.item_price_currency,
                itemPriceAmount=it.item_price_amount,
            )
            for it in item_rows
        ],
        postalCode=detail.postal_code if detail else None,
        stateOrRegion=detail.state_or_region if detail else None,
        city=detail.city if detail else None,
        detailAddress=detail.detail_address if detail else None,
        receiverName=detail.receiver_name if detail else None,
        detailFetchedAt=detail.fetched_at if detail else None,
    )


# ============================================================
# 2. 库存明细
# ============================================================
@router.get("/inventory", response_model=DataInventoryListOut)
async def list_inventory(
    country: str | None = Query(default=None),
    warehouse_id: str | None = Query(default=None),
    sku: str | None = Query(default=None),
    only_nonzero: bool = Query(default=True),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> DataInventoryListOut:
    base = (
        select(
            InventorySnapshotLatest,
            Warehouse.name.label("wh_name"),
            Warehouse.type.label("wh_type"),
        )
        .join(Warehouse, Warehouse.id == InventorySnapshotLatest.warehouse_id)
        .order_by(InventorySnapshotLatest.commodity_sku, Warehouse.id)
    )
    if country:
        base = base.where(InventorySnapshotLatest.country == country.upper())
    if warehouse_id:
        base = base.where(InventorySnapshotLatest.warehouse_id == warehouse_id)
    if sku:
        base = base.where(InventorySnapshotLatest.commodity_sku.ilike(f"%{sku}%"))
    if only_nonzero:
        base = base.where(
            (InventorySnapshotLatest.available > 0) | (InventorySnapshotLatest.reserved > 0)
        )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (await db.execute(base.offset((page - 1) * page_size).limit(page_size))).all()

    # 批量加载 commodity_name / main_image
    sku_codes = list({r[0].commodity_sku for r in rows})
    name_map: dict[str, tuple[str | None, str | None]] = {}
    if sku_codes:
        pl_rows = (
            await db.execute(
                select(
                    ProductListing.commodity_sku,
                    ProductListing.commodity_name,
                    ProductListing.main_image,
                ).where(ProductListing.commodity_sku.in_(sku_codes))
            )
        ).all()
        for sk, name, img in pl_rows:
            name_map.setdefault(sk, (name, img))

    items: list[DataInventoryItem] = []
    for inv, wh_name, wh_type in rows:
        name, image = name_map.get(inv.commodity_sku, (None, None))
        items.append(
            DataInventoryItem(
                commoditySku=inv.commodity_sku,
                commodityName=name,
                mainImage=image,
                warehouseId=inv.warehouse_id,
                warehouseName=wh_name,
                warehouseType=wh_type,
                country=inv.country,
                stockAvailable=inv.available,
                stockOccupy=inv.reserved,
                updatedAt=inv.updated_at,
            )
        )
    return DataInventoryListOut(items=items, total=int(total or 0), page=page, pageSize=page_size)


# ============================================================
# 3. 其他出库列表（在途数据）
# ============================================================
@router.get("/out-records", response_model=DataOutRecordListOut)
async def list_out_records(
    is_in_transit: bool | None = Query(default=True),
    country: str | None = Query(default=None),
    sku: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> DataOutRecordListOut:
    base = select(InTransitRecord).order_by(InTransitRecord.last_seen_at.desc())
    if is_in_transit is not None:
        base = base.where(InTransitRecord.is_in_transit.is_(is_in_transit))
    if country:
        base = base.where(InTransitRecord.target_country == country.upper())
    if sku:
        sub = (
            select(InTransitItem.saihu_out_record_id)
            .where(InTransitItem.commodity_sku.ilike(f"%{sku}%"))
            .subquery()
        )
        base = base.where(InTransitRecord.saihu_out_record_id.in_(select(sub.c.saihu_out_record_id)))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        (await db.execute(base.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    )

    # 批量加载 items
    record_ids = [r.saihu_out_record_id for r in rows]
    item_map: dict[str, list[InTransitItem]] = {}
    if record_ids:
        it_rows = (
            (
                await db.execute(
                    select(InTransitItem).where(InTransitItem.saihu_out_record_id.in_(record_ids))
                )
            )
            .scalars()
            .all()
        )
        for it in it_rows:
            item_map.setdefault(it.saihu_out_record_id, []).append(it)

    # 批量加载 warehouse 名称
    wh_ids = [r.target_warehouse_id for r in rows if r.target_warehouse_id]
    wh_name_map: dict[str, str] = {}
    if wh_ids:
        wh_rows = (
            await db.execute(
                select(Warehouse.id, Warehouse.name).where(Warehouse.id.in_(wh_ids))
            )
        ).all()
        wh_name_map = {wid: name for wid, name in wh_rows}

    items: list[DataOutRecord] = []
    for r in rows:
        sub_items = item_map.get(r.saihu_out_record_id, [])
        items.append(
            DataOutRecord(
                saihuOutRecordId=r.saihu_out_record_id,
                outWarehouseNo=r.out_warehouse_no,
                targetWarehouseId=r.target_warehouse_id,
                targetWarehouseName=wh_name_map.get(r.target_warehouse_id or "", None),
                targetCountry=r.target_country,
                remark=r.remark,
                status=r.status,
                isInTransit=r.is_in_transit,
                lastSeenAt=r.last_seen_at,
                items=[
                    DataOutRecordItem(commoditySku=it.commodity_sku, goods=it.goods)
                    for it in sub_items
                ],
            )
        )
    return DataOutRecordListOut(items=items, total=int(total or 0), page=page, pageSize=page_size)


# ============================================================
# 4. 仓库列表
# ============================================================
@router.get("/warehouses", response_model=DataWarehouseListOut)
async def list_data_warehouses(
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> DataWarehouseListOut:
    rows = (
        (await db.execute(select(Warehouse).order_by(Warehouse.country, Warehouse.id)))
        .scalars()
        .all()
    )
    items = [
        DataWarehouse(
            id=r.id,
            name=r.name,
            type=r.type,
            country=r.country,
            replenishSite=r.replenish_site_raw,
            lastSyncAt=r.last_sync_at,
        )
        for r in rows
    ]
    return DataWarehouseListOut(items=items, total=len(items))


# ============================================================
# 5. 店铺列表
# ============================================================
@router.get("/shops", response_model=DataShopListOut)
async def list_data_shops(
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> DataShopListOut:
    rows = (
        (await db.execute(select(Shop).order_by(Shop.marketplace_id, Shop.id))).scalars().all()
    )
    items = [
        DataShop(
            id=r.id,
            name=r.name,
            sellerId=r.seller_id,
            region=r.region,
            marketplaceId=r.marketplace_id,
            status=r.status,
            adStatus=r.ad_status,
            syncEnabled=r.sync_enabled,
            lastSyncAt=r.last_sync_at,
        )
        for r in rows
    ]
    return DataShopListOut(items=items, total=len(items))


# ============================================================
# 6. 在线产品信息
# ============================================================
@router.get("/product-listings", response_model=DataProductListingListOut)
async def list_product_listings_data(
    shop_id: str | None = Query(default=None),
    marketplace_id: str | None = Query(default=None),
    sku: str | None = Query(default=None, description="按 commodity_sku/seller_sku 模糊"),
    only_matched: bool | None = Query(default=None),
    only_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> DataProductListingListOut:
    base = select(ProductListing).order_by(ProductListing.commodity_sku, ProductListing.marketplace_id)
    if shop_id:
        base = base.where(ProductListing.shop_id == shop_id)
    if marketplace_id:
        base = base.where(ProductListing.marketplace_id == marketplace_id.upper())
    if sku:
        base = base.where(
            (ProductListing.commodity_sku.ilike(f"%{sku}%"))
            | (ProductListing.seller_sku.ilike(f"%{sku}%"))
        )
    if only_matched is not None:
        base = base.where(ProductListing.is_matched.is_(only_matched))
    if only_active is not None:
        base = base.where(
            ProductListing.online_status == ("active" if only_active else "inactive")
        )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        (await db.execute(base.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    )
    items = [
        DataProductListing(
            id=r.id,
            commoditySku=r.commodity_sku,
            commodityId=r.commodity_id,
            commodityName=r.commodity_name,
            mainImage=r.main_image,
            shopId=r.shop_id,
            marketplaceId=r.marketplace_id,
            sellerSku=r.seller_sku,
            parentSku=r.parent_sku,
            day7SaleNum=r.day7_sale_num,
            day14SaleNum=r.day14_sale_num,
            day30SaleNum=r.day30_sale_num,
            isMatched=r.is_matched,
            onlineStatus=r.online_status,
            lastSyncAt=r.last_sync_at,
        )
        for r in rows
    ]
    return DataProductListingListOut(
        items=items, total=int(total or 0), page=page, pageSize=page_size
    )


# ============================================================
# 7. sync_state 汇总（同步管理页用）
# ============================================================
@router.get("/sync-state")
async def list_sync_state(
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> list[dict]:
    from app.models.sync_state import SyncState

    rows = (await db.execute(select(SyncState).order_by(SyncState.job_name))).scalars().all()
    return [
        {
            "job_name": r.job_name,
            "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
            "last_success_at": r.last_success_at.isoformat() if r.last_success_at else None,
            "last_status": r.last_status,
            "last_error": r.last_error,
        }
        for r in rows
    ]
