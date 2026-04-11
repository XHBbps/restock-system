"""澶栭儴鏁版嵁婧愯娴?API銆?

READ-ONLY銆傛墍鏈夌鐐逛粠鏈湴鍚屾钀藉簱鐨勮〃鏌ヨ,杩斿洖涓庤禌鐙愭帴鍙?
鍩烘湰涓€鑷寸殑 camelCase 缁撴瀯,渚涢噰璐憳鎺掓煡"鍚屾杩涙潵鐨勬暟鎹槸鍚︽纭?銆?

瑕嗙洊鐨?7 涓祫婧?
- 璁㈠崟鍒楄〃 + 璁㈠崟璇︽儏(order_header / order_item / order_detail)
- 搴撳瓨鏄庣粏(inventory_snapshot_latest JOIN warehouse)
- 鍏朵粬鍑哄簱(in_transit_record + in_transit_item)
- 浠撳簱鍒楄〃(warehouse)
- 搴楅摵鍒楄〃(shop)
- 鍦ㄧ嚎浜у搧淇℃伅(product_listing)
"""

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import Float, case, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.api.deps import db_session, get_current_session
from app.core.exceptions import NotFound
from app.core.query import escape_like
from app.core.timezone import BEIJING
from app.models.in_transit import InTransitItem, InTransitRecord
from app.models.inventory import InventorySnapshotLatest
from app.models.order import OrderDetail, OrderHeader, OrderItem
from app.models.product_listing import ProductListing
from app.models.shop import Shop
from app.models.sku import SkuConfig
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
    DataSyncStateRow,
    DataWarehouse,
    DataWarehouseListOut,
    SkuOverviewListOut,
)

router = APIRouter(prefix="/api/data", tags=["data"])


def _disabled_order_detail_fields(detail: OrderDetail | None) -> dict[str, object | None]:
    return {
        "postal_code": detail.postal_code if detail else None,
        "state_or_region": None,
        "city": None,
        "detail_address": None,
        "receiver_name": None,
        "detail_fetched_at": detail.fetched_at if detail else None,
    }


def _has_visible_order_detail(detail: OrderDetail | None) -> bool:
    if detail is None:
        return False
    return any(
        bool(value and str(value).strip())
        for value in (
            detail.postal_code,
            detail.state_or_region,
            detail.city,
            detail.detail_address,
            detail.receiver_name,
        )
    )


def _product_listing_active_predicate(only_active: bool) -> ColumnElement[bool]:
    normalized = func.lower(ProductListing.online_status)
    return normalized == "active" if only_active else normalized != "active"


ORDER_STATUS_SORT_ORDER: dict[str, int] = {
    "Pending": 0,
    "Unshipped": 1,
    "PartiallyShipped": 2,
    "Shipped": 3,
    "Canceled": 4,
}

OUT_RECORD_IN_TRANSIT_SORT_ORDER = 0
OUT_RECORD_INACTIVE_SORT_ORDER = 1


def _apply_direction(
    columns: tuple[ColumnElement[object], ...], sort_order: str
) -> list[ColumnElement[object]]:
    return [column.asc() if sort_order == "asc" else column.desc() for column in columns]


def _order_item_count_expr() -> ColumnElement[int]:
    return select(func.count()).where(OrderItem.order_id == OrderHeader.id).scalar_subquery()


def _order_has_detail_expr() -> ColumnElement[int]:
    visible_detail_count = (
        select(func.count())
        .where(
            OrderDetail.shop_id == OrderHeader.shop_id,
            OrderDetail.amazon_order_id == OrderHeader.amazon_order_id,
            or_(
                OrderDetail.postal_code.is_not(None),
                OrderDetail.state_or_region.is_not(None),
                OrderDetail.city.is_not(None),
                OrderDetail.detail_address.is_not(None),
                OrderDetail.receiver_name.is_not(None),
            ),
        )
        .scalar_subquery()
    )
    return case((visible_detail_count > 0, 1), else_=0)


def _order_status_sort_expr() -> ColumnElement[int]:
    return case(
        *[
            (OrderHeader.order_status == status, order)
            for status, order in ORDER_STATUS_SORT_ORDER.items()
        ],
        else_=len(ORDER_STATUS_SORT_ORDER),
    )


def _apply_order_sort(stmt, sort_by: str | None, sort_order: str):
    item_count_expr = _order_item_count_expr()
    has_detail_expr = _order_has_detail_expr()
    amount_expr = func.coalesce(OrderHeader.order_total_amount.cast(Float), -1.0)
    sort_map: dict[str, tuple[ColumnElement[object], ...]] = {
        "amazonOrderId": (OrderHeader.amazon_order_id,),
        "shopId": (OrderHeader.shop_id,),
        "countryCode": (OrderHeader.country_code,),
        "orderStatus": (_order_status_sort_expr(),),
        "orderTotalAmount": (
            case((OrderHeader.order_total_amount.is_(None), 1), else_=0),
            amount_expr,
        ),
        "itemCount": (item_count_expr,),
        "hasDetail": (has_detail_expr,),
        "purchaseDate": (OrderHeader.purchase_date,),
    }
    columns = sort_map.get(sort_by or "", (OrderHeader.purchase_date,))
    return stmt.order_by(
        *_apply_direction(columns, sort_order),
        OrderHeader.purchase_date.desc(),
        OrderHeader.id.desc(),
    )


def _apply_inventory_sort(stmt, sort_by: str | None, sort_order: str):
    sort_map: dict[str, tuple[ColumnElement[object], ...]] = {
        "commoditySku": (InventorySnapshotLatest.commodity_sku,),
        "warehouseName": (
            case((Warehouse.name.is_(None), 1), else_=0),
            Warehouse.name,
        ),
        "country": (
            case((InventorySnapshotLatest.country.is_(None), 1), else_=0),
            InventorySnapshotLatest.country,
        ),
        "stockAvailable": (InventorySnapshotLatest.available,),
        "stockOccupy": (InventorySnapshotLatest.reserved,),
        "updatedAt": (InventorySnapshotLatest.updated_at,),
    }
    columns = sort_map.get(sort_by or "", (InventorySnapshotLatest.commodity_sku, Warehouse.id))
    return stmt.order_by(
        *_apply_direction(columns, sort_order),
        InventorySnapshotLatest.commodity_sku.asc(),
        Warehouse.id.asc(),
    )


def _out_record_item_count_expr() -> ColumnElement[int]:
    return (
        select(func.count())
        .where(InTransitItem.saihu_out_record_id == InTransitRecord.saihu_out_record_id)
        .scalar_subquery()
    )


def _out_record_goods_total_expr() -> ColumnElement[int]:
    return (
        select(func.coalesce(func.sum(InTransitItem.goods), 0))
        .where(InTransitItem.saihu_out_record_id == InTransitRecord.saihu_out_record_id)
        .scalar_subquery()
    )


def _out_record_target_warehouse_name_expr() -> ColumnElement[str | None]:
    return (
        select(Warehouse.name)
        .where(Warehouse.id == InTransitRecord.target_warehouse_id)
        .scalar_subquery()
    )


def _out_record_status_sort_expr() -> ColumnElement[int]:
    return case(
        (InTransitRecord.is_in_transit.is_(True), OUT_RECORD_IN_TRANSIT_SORT_ORDER),
        else_=OUT_RECORD_INACTIVE_SORT_ORDER,
    )


def _apply_out_record_sort(stmt, sort_by: str | None, sort_order: str):
    target_warehouse_name_expr = _out_record_target_warehouse_name_expr()
    item_count_expr = _out_record_item_count_expr()
    goods_total_expr = _out_record_goods_total_expr()
    sort_map: dict[str, tuple[ColumnElement[object], ...]] = {
        "outWarehouseNo": (
            case((InTransitRecord.out_warehouse_no.is_(None), 1), else_=0),
            InTransitRecord.out_warehouse_no,
        ),
        "saihuOutRecordId": (InTransitRecord.saihu_out_record_id,),
        "targetWarehouseName": (
            case((target_warehouse_name_expr.is_(None), 1), else_=0),
            target_warehouse_name_expr,
        ),
        "targetCountry": (
            case((InTransitRecord.target_country.is_(None), 1), else_=0),
            InTransitRecord.target_country,
        ),
        "itemCount": (item_count_expr,),
        "goodsTotal": (goods_total_expr,),
        "status": (_out_record_status_sort_expr(),),
        "lastSeenAt": (InTransitRecord.last_seen_at,),
    }
    columns = sort_map.get(sort_by or "", (InTransitRecord.last_seen_at,))
    return stmt.order_by(
        *_apply_direction(columns, sort_order),
        InTransitRecord.last_seen_at.desc(),
        InTransitRecord.saihu_out_record_id.desc(),
    )


# ============================================================
# 1. 璁㈠崟鍒楄〃 + 璇︽儏
# ============================================================
@router.get("/orders", response_model=DataOrderListOut)
async def list_orders(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    country: str | None = Query(default=None),
    status: str | None = Query(default=None),
    sku: str | None = Query(
        default=None, description="鎸?commodity_sku 鎴?amazon_order_id 妯＄硦鍖归厤"
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=5000),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> DataOrderListOut:
    base = select(OrderHeader)

    if date_from:
        base = base.where(
            OrderHeader.purchase_date
            >= datetime.combine(date_from, datetime.min.time(), tzinfo=BEIJING)
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
        # 鍦?amazon_order_id 鎴栭€氳繃 order_item JOIN 鍖归厤 commodity_sku
        subq = (
            select(OrderItem.order_id)
            .where(OrderItem.commodity_sku.ilike(f"%{escape_like(sku)}%", escape="\\"))
            .subquery()
        )
        base = base.where(
            (OrderHeader.amazon_order_id.ilike(f"%{escape_like(sku)}%", escape="\\"))
            | (OrderHeader.id.in_(select(subq.c.order_id)))
        )

    base = _apply_order_sort(base, sort_by, sort_order)
    total = (
        await db.execute(select(func.count()).select_from(base.order_by(None).subquery()))
    ).scalar_one()
    rows = (await db.execute(base.offset((page - 1) * page_size).limit(page_size))).scalars().all()

    # 鎵归噺鍔犺浇 items 涓?detail 鏍囧織
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
        # * 蹇呴』鐢ㄥ鍚堥敭杩囨护銆傚彧鎸?shop_id IN(...) 浼氭媺鍥炶 shop 鐨勫叏閮ㄥ巻鍙?detail,
        # 鍦ㄦ暟鎹噺澶ф椂閫犳垚鍐呭瓨鐖嗙偢(review H-N1)銆?
        det_rows = (
            (
                await db.execute(
                    select(OrderDetail).where(
                        tuple_(OrderDetail.shop_id, OrderDetail.amazon_order_id).in_(keys)
                    )
                )
            )
            .scalars()
            .all()
        )
        detail_set = {
            (detail.shop_id, detail.amazon_order_id)
            for detail in det_rows
            if _has_visible_order_detail(detail)
        }

    items = [
        DataOrderSummary.model_validate(
            {
                **{
                    k: getattr(r, k)
                    for k in (
                        "shop_id",
                        "amazon_order_id",
                        "marketplace_id",
                        "country_code",
                        "order_status",
                        "order_total_currency",
                        "order_total_amount",
                        "fulfillment_channel",
                        "purchase_date",
                        "last_update_date",
                        "refund_status",
                        "last_sync_at",
                    )
                },
                "has_detail": (r.shop_id, r.amazon_order_id) in detail_set,
                "item_count": item_count_map.get(r.id, 0),
            }
        )
        for r in rows
    ]
    return DataOrderListOut(items=items, total=int(total or 0), page=page, page_size=page_size)


@router.get("/orders/{shop_id}/{amazon_order_id}", response_model=DataOrderDetail)
async def get_order_detail(
    shop_id: str = Path(...),
    amazon_order_id: str = Path(...),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> DataOrderDetail:
    header = (
        await db.execute(
            select(OrderHeader).where(
                (OrderHeader.shop_id == shop_id) & (OrderHeader.amazon_order_id == amazon_order_id)
            )
        )
    ).scalar_one_or_none()
    if header is None:
        raise NotFound(f"订单 {shop_id}/{amazon_order_id} 不存在")

    item_rows = (
        (await db.execute(select(OrderItem).where(OrderItem.order_id == header.id))).scalars().all()
    )

    detail = (
        await db.execute(
            select(OrderDetail).where(
                (OrderDetail.shop_id == shop_id) & (OrderDetail.amazon_order_id == amazon_order_id)
            )
        )
    ).scalar_one_or_none()

    # 鐢?from_attributes 鎶?ORM header 鐩存帴鏄犲皠鍒?DTO,detail 瀛楁鎵嬪姩琛?
    return DataOrderDetail.model_validate(
        {
            **{
                k: getattr(header, k)
                for k in (
                    "shop_id",
                    "amazon_order_id",
                    "marketplace_id",
                    "country_code",
                    "order_status",
                    "order_total_currency",
                    "order_total_amount",
                    "fulfillment_channel",
                    "purchase_date",
                    "last_update_date",
                    "refund_status",
                    "is_buyer_requested_cancel",
                    "last_sync_at",
                )
            },
            "items": [DataOrderItem.model_validate(it) for it in item_rows],
            **_disabled_order_detail_fields(detail),
        }
    )


# ============================================================
# 2. 搴撳瓨鏄庣粏
# ============================================================
@router.get("/inventory", response_model=DataInventoryListOut)
async def list_inventory(
    country: str | None = Query(default=None),
    warehouse_id: str | None = Query(default=None),
    sku: str | None = Query(default=None),
    only_nonzero: bool = Query(default=True),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=5000),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> DataInventoryListOut:
    base = select(
        InventorySnapshotLatest,
        Warehouse.name.label("wh_name"),
        Warehouse.type.label("wh_type"),
    ).join(Warehouse, Warehouse.id == InventorySnapshotLatest.warehouse_id)
    if country:
        base = base.where(InventorySnapshotLatest.country == country.upper())
    if warehouse_id:
        base = base.where(InventorySnapshotLatest.warehouse_id == warehouse_id)
    if sku:
        base = base.where(
            InventorySnapshotLatest.commodity_sku.ilike(f"%{escape_like(sku)}%", escape="\\")
        )
    if only_nonzero:
        base = base.where(
            (InventorySnapshotLatest.available > 0) | (InventorySnapshotLatest.reserved > 0)
        )

    base = _apply_inventory_sort(base, sort_by, sort_order)
    total = (
        await db.execute(select(func.count()).select_from(base.order_by(None).subquery()))
    ).scalar_one()
    rows = (await db.execute(base.offset((page - 1) * page_size).limit(page_size))).all()

    # 鎵归噺鍔犺浇 commodity_name / main_image
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
            DataInventoryItem.model_validate(
                {
                    "commodity_sku": inv.commodity_sku,
                    "commodity_name": name,
                    "main_image": image,
                    "warehouse_id": inv.warehouse_id,
                    "warehouse_name": wh_name,
                    "warehouse_type": wh_type,
                    "country": inv.country,
                    "stock_available": inv.available,
                    "stock_occupy": inv.reserved,
                    "updated_at": inv.updated_at,
                }
            )
        )
    return DataInventoryListOut(items=items, total=int(total or 0), page=page, page_size=page_size)


# ============================================================
# 3. 鍏朵粬鍑哄簱鍒楄〃(鍦ㄩ€旀暟鎹?
# ============================================================
@router.get("/out-records", response_model=DataOutRecordListOut)
async def list_out_records(
    is_in_transit: bool | None = Query(default=True),
    country: str | None = Query(default=None),
    sku: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=5000),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> DataOutRecordListOut:
    base = select(InTransitRecord)
    if is_in_transit is not None:
        base = base.where(InTransitRecord.is_in_transit.is_(is_in_transit))
    if country:
        base = base.where(InTransitRecord.target_country == country.upper())
    if sku:
        sub = (
            select(InTransitItem.saihu_out_record_id)
            .where(InTransitItem.commodity_sku.ilike(f"%{escape_like(sku)}%", escape="\\"))
            .subquery()
        )
        base = base.where(
            InTransitRecord.saihu_out_record_id.in_(select(sub.c.saihu_out_record_id))
        )

    base = _apply_out_record_sort(base, sort_by, sort_order)
    total = (
        await db.execute(select(func.count()).select_from(base.order_by(None).subquery()))
    ).scalar_one()
    rows = (await db.execute(base.offset((page - 1) * page_size).limit(page_size))).scalars().all()

    # 鎵归噺鍔犺浇 items
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

    # 鎵归噺鍔犺浇 warehouse 鍚嶇О
    wh_ids = [r.target_warehouse_id for r in rows if r.target_warehouse_id]
    wh_name_map: dict[str, str] = {}
    if wh_ids:
        wh_rows = (
            await db.execute(select(Warehouse.id, Warehouse.name).where(Warehouse.id.in_(wh_ids)))
        ).all()
        wh_name_map = dict(wh_rows)

    items: list[DataOutRecord] = []
    for r in rows:
        sub_items = item_map.get(r.saihu_out_record_id, [])
        items.append(
            DataOutRecord.model_validate(
                {
                    "saihu_out_record_id": r.saihu_out_record_id,
                    "out_warehouse_no": r.out_warehouse_no,
                    "target_warehouse_id": r.target_warehouse_id,
                    "target_warehouse_name": wh_name_map.get(r.target_warehouse_id or ""),
                    "target_country": r.target_country,
                    "remark": r.remark,
                    "status": r.status,
                    "is_in_transit": r.is_in_transit,
                    "last_seen_at": r.last_seen_at,
                    "items": [DataOutRecordItem.model_validate(it) for it in sub_items],
                }
            )
        )
    return DataOutRecordListOut(items=items, total=int(total or 0), page=page, page_size=page_size)


# ============================================================
# 4. 浠撳簱鍒楄〃
# ============================================================
@router.get("/warehouses", response_model=DataWarehouseListOut)
async def list_data_warehouses(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=500, ge=1, le=1000),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> DataWarehouseListOut:
    stock_subquery = (
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

    total = (await db.execute(select(func.count()).select_from(Warehouse))).scalar_one()

    rows = (
        await db.execute(
            select(
                Warehouse,
                func.coalesce(stock_subquery.c.total_stock, 0).label("total_stock"),
            )
            .outerjoin(stock_subquery, stock_subquery.c.warehouse_id == Warehouse.id)
            .order_by(Warehouse.country, Warehouse.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).all()
    items = [
        DataWarehouse.model_validate(
            {
                "id": warehouse.id,
                "name": warehouse.name,
                "type": warehouse.type,
                "country": warehouse.country,
                "replenish_site": warehouse.replenish_site_raw,
                "total_stock": int(total_stock or 0),
                "last_sync_at": warehouse.last_sync_at,
            }
        )
        for warehouse, total_stock in rows
    ]
    return DataWarehouseListOut(
        items=items,
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )


# ============================================================
# 5. 搴楅摵鍒楄〃
# ============================================================
@router.get("/shops", response_model=DataShopListOut)
async def list_data_shops(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=500, ge=1, le=1000),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> DataShopListOut:
    total = (await db.execute(select(func.count()).select_from(Shop))).scalar_one()
    rows = (
        await db.execute(
            select(Shop)
            .order_by(Shop.marketplace_id, Shop.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).scalars().all()
    items = [DataShop.model_validate(r) for r in rows]
    return DataShopListOut(
        items=items,
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )


# ============================================================
# 6. 鍦ㄧ嚎浜у搧淇℃伅
# ============================================================
@router.get("/product-listings", response_model=DataProductListingListOut)
async def list_product_listings_data(
    shop_id: str | None = Query(default=None),
    marketplace_id: str | None = Query(default=None),
    sku: str | None = Query(default=None, description="鎸?commodity_sku/seller_sku 妯＄硦"),
    only_matched: bool | None = Query(default=None),
    only_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=5000),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> DataProductListingListOut:
    base = select(ProductListing).order_by(
        ProductListing.commodity_sku, ProductListing.marketplace_id
    )
    if shop_id:
        base = base.where(ProductListing.shop_id == shop_id)
    if marketplace_id:
        base = base.where(ProductListing.marketplace_id == marketplace_id.upper())
    if sku:
        base = base.where(
            (ProductListing.commodity_sku.ilike(f"%{escape_like(sku)}%", escape="\\"))
            | (ProductListing.seller_sku.ilike(f"%{escape_like(sku)}%", escape="\\"))
        )
    if only_matched is not None:
        base = base.where(ProductListing.is_matched.is_(only_matched))
    if only_active is not None:
        base = base.where(_product_listing_active_predicate(only_active))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (await db.execute(base.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    items = [DataProductListing.model_validate(r) for r in rows]
    return DataProductListingListOut(
        items=items, total=int(total or 0), page=page, page_size=page_size
    )


# ============================================================
# 7. SKU Overview (grouped by SKU config)
# ============================================================
@router.get("/sku-overview", response_model=SkuOverviewListOut)
async def list_sku_overview(
    keyword: str | None = Query(default=None, description="鎸?commodity_sku 妯＄硦鎼滅储"),
    enabled: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=5000),
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> SkuOverviewListOut:
    """Return SKU-level overview: config + aggregated listings, paginated by SKU."""
    from app.schemas.data import SkuListingItem, SkuOverviewItem

    base = select(SkuConfig).order_by(SkuConfig.commodity_sku)
    if enabled is not None:
        base = base.where(SkuConfig.enabled.is_(enabled))
    if keyword:
        base = base.where(SkuConfig.commodity_sku.ilike(f"%{escape_like(keyword)}%", escape="\\"))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    sku_rows = (
        (await db.execute(base.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    )

    if not sku_rows:
        return SkuOverviewListOut(items=[], total=int(total or 0), page=page, page_size=page_size)

    sku_codes = [r.commodity_sku for r in sku_rows]

    listing_rows = (
        (
            await db.execute(
                select(ProductListing)
                .where(ProductListing.commodity_sku.in_(sku_codes))
                .order_by(ProductListing.commodity_sku, ProductListing.marketplace_id)
            )
        )
        .scalars()
        .all()
    )

    listings_by_sku: dict[str, list[Any]] = {}
    for pl in listing_rows:
        listings_by_sku.setdefault(pl.commodity_sku, []).append(pl)

    items: list[SkuOverviewItem] = []
    for sku_cfg in sku_rows:
        sku = sku_cfg.commodity_sku
        sku_listings = listings_by_sku.get(sku, [])
        name = sku_listings[0].commodity_name if sku_listings else None
        image = sku_listings[0].main_image if sku_listings else None
        total_day30 = sum((pl.day30_sale_num or 0) for pl in sku_listings)

        items.append(
            SkuOverviewItem(
                commodity_sku=sku,
                commodity_name=name,
                main_image=image,
                enabled=sku_cfg.enabled,
                lead_time_days=sku_cfg.lead_time_days,
                listing_count=len(sku_listings),
                total_day30_sales=total_day30,
                listings=[
                    SkuListingItem(
                        id=pl.id,
                        shop_id=pl.shop_id,
                        marketplace_id=pl.marketplace_id,
                        seller_sku=pl.seller_sku,
                        day7_sale_num=pl.day7_sale_num,
                        day14_sale_num=pl.day14_sale_num,
                        day30_sale_num=pl.day30_sale_num,
                        online_status=pl.online_status or "",
                        last_sync_at=pl.last_sync_at.isoformat() if pl.last_sync_at else None,
                    )
                    for pl in sku_listings
                ],
            )
        )

    return SkuOverviewListOut(items=items, total=int(total or 0), page=page, page_size=page_size)


# ============================================================
# 8. sync_state 姹囨€?鍚屾绠＄悊椤电敤)
# ============================================================
@router.get("/sync-state", response_model=list[DataSyncStateRow])
async def list_sync_state(
    db: AsyncSession = Depends(db_session),
    _: dict[str, Any] = Depends(get_current_session),
) -> list[DataSyncStateRow]:
    from app.models.sync_state import SyncState

    rows = (await db.execute(select(SyncState).order_by(SyncState.job_name))).scalars().all()
    return [
        DataSyncStateRow(
            job_name=r.job_name,
            last_run_at=r.last_run_at,
            last_success_at=r.last_success_at,
            last_status=r.last_status,
            last_error=r.last_error,
        )
        for r in rows
    ]
