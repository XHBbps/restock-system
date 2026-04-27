"""外部数据源观测 API。

READ-ONLY。所有端点从本地同步落库的表查询,返回与赛狐接口
基本一致的 camelCase 结构,供采购员排查"同步进来的数据是否正确"。

覆盖的 7 个资源:
- 订单列表 + 订单详情(order_header / order_item / order_detail)
- 库存明细(inventory_snapshot_latest JOIN warehouse)
- 其他出库(in_transit_record + in_transit_item)
- 仓库列表(warehouse)
- 店铺列表(shop)
- 在线产品信息(product_listing)
"""

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import Float, case, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.api.deps import db_session_readonly, require_permission
from app.core.exceptions import NotFound
from app.core.permissions import DATA_BASE_VIEW, DATA_BIZ_VIEW, SYNC_VIEW
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
    DataInventoryWarehouseGroup,
    DataInventoryWarehouseGroupListOut,
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
    columns: tuple[Any, ...], sort_order: str
) -> list[Any]:
    # 与 api/suggestion.py 同样的妥协：InstrumentedAttribute[T] 不是
    # ColumnElement[object] 的子类（参数不协变），用 tuple[Any, ...] 最宽松
    return [column.asc() if sort_order == "asc" else column.desc() for column in columns]


def _order_item_count_expr() -> ColumnElement[int]:
    return select(func.count()).where(OrderItem.order_id == OrderHeader.id).scalar_subquery()


def _order_has_detail_expr() -> ColumnElement[int]:
    visible_detail_exists = (
        select(func.count())
        .where(
            OrderDetail.shop_id == OrderHeader.shop_id,
            OrderDetail.amazon_order_id == OrderHeader.amazon_order_id,
            _order_detail_visible_predicate(),
        )
        .scalar_subquery()
    )
    return case((visible_detail_exists > 0, 1), else_=0)


def _order_detail_visible_predicate() -> ColumnElement[bool]:
    return or_(
        OrderDetail.postal_code.is_not(None),
        OrderDetail.state_or_region.is_not(None),
        OrderDetail.city.is_not(None),
        OrderDetail.detail_address.is_not(None),
        OrderDetail.receiver_name.is_not(None),
    )


def _order_status_sort_expr() -> ColumnElement[int]:
    return case(
        *[
            (OrderHeader.order_status == status, order)
            for status, order in ORDER_STATUS_SORT_ORDER.items()
        ],
        else_=len(ORDER_STATUS_SORT_ORDER),
    )


def _apply_order_sort(stmt: Any, sort_by: str | None, sort_order: str) -> Any:
    item_count_expr = _order_item_count_expr()
    has_detail_expr = _order_has_detail_expr()
    amount_expr = func.coalesce(OrderHeader.order_total_amount.cast(Float), -1.0)
    sort_map: dict[str, tuple[Any, ...]] = {
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


def _apply_inventory_sort(stmt: Any, sort_by: str | None, sort_order: str) -> Any:
    sort_map: dict[str, tuple[Any, ...]] = {
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


def _apply_inventory_filters(
    stmt: Any,
    *,
    country: str | None,
    warehouse_id: str | None = None,
    sku: str | None,
    only_nonzero: bool,
    is_package: bool | None = None,
) -> Any:
    if country:
        stmt = stmt.where(InventorySnapshotLatest.country == country.upper())
    if warehouse_id:
        stmt = stmt.where(InventorySnapshotLatest.warehouse_id == warehouse_id)
    if sku:
        stmt = stmt.where(
            InventorySnapshotLatest.commodity_sku.ilike(f"%{escape_like(sku)}%", escape="\\")
        )
    if only_nonzero:
        stmt = stmt.where(
            (InventorySnapshotLatest.available > 0) | (InventorySnapshotLatest.reserved > 0)
        )
    if is_package is not None:
        listing_exists = (
            select(ProductListing.id)
            .where(ProductListing.commodity_sku == InventorySnapshotLatest.commodity_sku)
            .exists()
        )
        stmt = stmt.where(~listing_exists if is_package else listing_exists)
    return stmt


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


def _apply_out_record_sort(stmt: Any, sort_by: str | None, sort_order: str) -> Any:
    target_warehouse_name_expr = _out_record_target_warehouse_name_expr()
    item_count_expr = _out_record_item_count_expr()
    goods_total_expr = _out_record_goods_total_expr()
    sort_map: dict[str, tuple[Any, ...]] = {
        "warehouseId": (
            case((InTransitRecord.warehouse_id.is_(None), 1), else_=0),
            InTransitRecord.warehouse_id,
        ),
        "outWarehouseNo": (
            case((InTransitRecord.out_warehouse_no.is_(None), 1), else_=0),
            InTransitRecord.out_warehouse_no,
        ),
        "saihuOutRecordId": (InTransitRecord.saihu_out_record_id,),
        "updateTime": (
            case((InTransitRecord.update_time.is_(None), 1), else_=0),
            InTransitRecord.update_time,
        ),
        "typeName": (
            case((InTransitRecord.type_name.is_(None), 1), else_=0),
            InTransitRecord.type_name,
        ),
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
        "type": (InTransitRecord.type,),
        "lastSeenAt": (InTransitRecord.last_seen_at,),
    }
    columns = sort_map.get(sort_by or "", (InTransitRecord.update_time, InTransitRecord.last_seen_at))
    return stmt.order_by(
        *_apply_direction(columns, sort_order),
        InTransitRecord.update_time.desc(),
        InTransitRecord.last_seen_at.desc(),
        InTransitRecord.saihu_out_record_id.desc(),
    )


# ============================================================
# 1. 订单列表 + 详情
# ============================================================
@router.get("/orders", response_model=DataOrderListOut)
async def list_orders(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    country: str | None = Query(default=None),
    shop_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    sku: str | None = Query(
        default=None, description="按 commodity_sku 或 amazon_order_id 模糊匹配"
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=5000),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BIZ_VIEW)),
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
    if shop_id:
        base = base.where(OrderHeader.shop_id == shop_id)
    if status:
        base = base.where(OrderHeader.order_status == status)
    if sku:
        # 在 amazon_order_id 或通过 order_item JOIN 匹配 commodity_sku
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
        # * 必须用复合键过滤。只按 shop_id IN(...) 会拉回该 shop 的全部历史 detail,
        # 在数据量大时造成内存爆炸(review H-N1)。
        det_rows = (
            (
                await db.execute(
                    select(OrderDetail.shop_id, OrderDetail.amazon_order_id).where(
                        tuple_(OrderDetail.shop_id, OrderDetail.amazon_order_id).in_(keys),
                        _order_detail_visible_predicate(),
                    )
                )
            )
            .all()
        )
        detail_set = {(shop_id, amazon_order_id) for shop_id, amazon_order_id in det_rows}

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
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BIZ_VIEW)),
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

    # 用 from_attributes 把 ORM header 直接映射到 DTO,detail 字段手动补
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
# 2. 库存明细
# ============================================================
@router.get("/inventory", response_model=DataInventoryListOut)
async def list_inventory(
    country: str | None = Query(default=None),
    warehouse_id: str | None = Query(default=None),
    sku: str | None = Query(default=None),
    only_nonzero: bool = Query(default=True),
    is_package: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=5000),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BIZ_VIEW)),
) -> DataInventoryListOut:
    base = select(
        InventorySnapshotLatest,
        Warehouse.name.label("wh_name"),
        Warehouse.type.label("wh_type"),
    ).join(Warehouse, Warehouse.id == InventorySnapshotLatest.warehouse_id)
    base = _apply_inventory_filters(
        base,
        country=country,
        warehouse_id=warehouse_id,
        sku=sku,
        only_nonzero=only_nonzero,
        is_package=is_package,
    )

    base = _apply_inventory_sort(base, sort_by, sort_order)
    total = (
        await db.execute(select(func.count()).select_from(base.order_by(None).subquery()))
    ).scalar_one()
    rows = (await db.execute(base.offset((page - 1) * page_size).limit(page_size))).all()

    # 批量加载 commodity_name / main_image
    sku_codes = list({r[0].commodity_sku for r in rows})
    name_map: dict[str, tuple[str | None, str | None]] = {}
    matched_skus: set[str] = set()
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
            if sk is not None:
                matched_skus.add(sk)
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
                    "is_package": inv.commodity_sku not in matched_skus,
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


@router.get("/inventory/warehouse-groups", response_model=DataInventoryWarehouseGroupListOut)
async def list_inventory_warehouse_groups(
    country: str | None = Query(default=None),
    sku: str | None = Query(default=None),
    only_nonzero: bool = Query(default=True),
    is_package: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BIZ_VIEW)),
) -> DataInventoryWarehouseGroupListOut:
    group_stmt = (
        select(
            InventorySnapshotLatest.warehouse_id.label("warehouse_id"),
            Warehouse.name.label("warehouse_name"),
            Warehouse.type.label("warehouse_type"),
            func.count().label("sku_count"),
            func.coalesce(func.sum(InventorySnapshotLatest.available), 0).label("total_available"),
            func.coalesce(func.sum(InventorySnapshotLatest.reserved), 0).label("total_occupy"),
        )
        .join(Warehouse, Warehouse.id == InventorySnapshotLatest.warehouse_id)
        .group_by(InventorySnapshotLatest.warehouse_id, Warehouse.name, Warehouse.type)
        .order_by(Warehouse.name.asc(), InventorySnapshotLatest.warehouse_id.asc())
    )
    group_stmt = _apply_inventory_filters(
        group_stmt,
        country=country,
        sku=sku,
        only_nonzero=only_nonzero,
        is_package=is_package,
    )

    grouped_subquery = group_stmt.order_by(None).subquery()
    total = (await db.execute(select(func.count()).select_from(grouped_subquery))).scalar_one()
    group_rows = (
        await db.execute(group_stmt.offset((page - 1) * page_size).limit(page_size))
    ).all()

    warehouse_ids = [row.warehouse_id for row in group_rows]
    if not warehouse_ids:
        return DataInventoryWarehouseGroupListOut(
            items=[],
            total=int(total or 0),
            page=page,
            page_size=page_size,
        )

    item_stmt = (
        select(
            InventorySnapshotLatest,
            Warehouse.name.label("wh_name"),
            Warehouse.type.label("wh_type"),
        )
        .join(Warehouse, Warehouse.id == InventorySnapshotLatest.warehouse_id)
        .where(InventorySnapshotLatest.warehouse_id.in_(warehouse_ids))
        .order_by(Warehouse.name.asc(), InventorySnapshotLatest.warehouse_id.asc(), InventorySnapshotLatest.commodity_sku.asc())
    )
    item_stmt = _apply_inventory_filters(
        item_stmt,
        country=country,
        sku=sku,
        only_nonzero=only_nonzero,
        is_package=is_package,
    )
    item_rows = (await db.execute(item_stmt)).all()

    sku_codes = list({row[0].commodity_sku for row in item_rows})
    name_map: dict[str, tuple[str | None, str | None]] = {}
    matched_skus: set[str] = set()
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
            if sk is not None:
                matched_skus.add(sk)
                name_map.setdefault(sk, (name, img))

    items_by_warehouse: dict[str, list[DataInventoryItem]] = {warehouse_id: [] for warehouse_id in warehouse_ids}
    for inv, wh_name, wh_type in item_rows:
        name, image = name_map.get(inv.commodity_sku, (None, None))
        items_by_warehouse.setdefault(inv.warehouse_id, []).append(
            DataInventoryItem.model_validate(
                {
                    "commodity_sku": inv.commodity_sku,
                    "commodity_name": name,
                    "main_image": image,
                    "is_package": inv.commodity_sku not in matched_skus,
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

    groups = [
        DataInventoryWarehouseGroup.model_validate(
            {
                "warehouse_id": row.warehouse_id,
                "warehouse_name": row.warehouse_name,
                "warehouse_type": row.warehouse_type,
                "sku_count": int(row.sku_count or 0),
                "total_available": int(row.total_available or 0),
                "total_occupy": int(row.total_occupy or 0),
                "items": items_by_warehouse.get(row.warehouse_id, []),
            }
        )
        for row in group_rows
    ]
    return DataInventoryWarehouseGroupListOut(
        items=groups,
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )


# ============================================================
# 3. 其他出库列表(在途数据)
# ============================================================
@router.get("/out-record-types", response_model=list[str])
async def list_out_record_types(
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BIZ_VIEW)),
) -> list[str]:
    rows = (
        await db.execute(
            select(InTransitRecord.type_name)
            .where(InTransitRecord.type_name.is_not(None), InTransitRecord.type_name != "")
            .distinct()
            .order_by(InTransitRecord.type_name)
        )
    ).all()
    return [type_name for (type_name,) in rows if type_name]


@router.get("/out-records", response_model=DataOutRecordListOut)
async def list_out_records(
    is_in_transit: bool | None = Query(default=None),
    country: str | None = Query(default=None),
    type_name: str | None = Query(default=None),
    sku: str | None = Query(default=None),
    out_warehouse_no: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=5000),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BIZ_VIEW)),
) -> DataOutRecordListOut:
    base = select(InTransitRecord)
    if is_in_transit is not None:
        base = base.where(InTransitRecord.is_in_transit.is_(is_in_transit))
    if country:
        base = base.where(InTransitRecord.target_country == country.upper())
    if type_name:
        base = base.where(InTransitRecord.type_name == type_name)
    if sku:
        sub = (
            select(InTransitItem.saihu_out_record_id)
            .where(InTransitItem.commodity_sku.ilike(f"%{escape_like(sku)}%", escape="\\"))
            .subquery()
        )
        base = base.where(
            InTransitRecord.saihu_out_record_id.in_(select(sub.c.saihu_out_record_id))
        )
    if out_warehouse_no:
        base = base.where(
            InTransitRecord.out_warehouse_no.ilike(
                f"%{escape_like(out_warehouse_no)}%",
                escape="\\",
            )
        )

    base = _apply_out_record_sort(base, sort_by, sort_order)
    total = (
        await db.execute(select(func.count()).select_from(base.order_by(None).subquery()))
    ).scalar_one()
    rows = (await db.execute(base.offset((page - 1) * page_size).limit(page_size))).scalars().all()

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
            await db.execute(select(Warehouse.id, Warehouse.name).where(Warehouse.id.in_(wh_ids)))
        ).all()
        wh_name_map = {row[0]: row[1] for row in wh_rows}

    items: list[DataOutRecord] = []
    for r in rows:
        sub_items = item_map.get(r.saihu_out_record_id, [])
        items.append(
            DataOutRecord.model_validate(
                {
                    "saihu_out_record_id": r.saihu_out_record_id,
                    "warehouse_id": r.warehouse_id,
                    "out_warehouse_no": r.out_warehouse_no,
                    "target_warehouse_id": r.target_warehouse_id,
                    "target_warehouse_name": wh_name_map.get(r.target_warehouse_id or ""),
                    "target_country": r.target_country,
                    "update_time": r.update_time,
                    "type": r.type,
                    "type_name": r.type_name,
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
# 4. 仓库列表
# ============================================================
@router.get("/warehouses", response_model=DataWarehouseListOut)
async def list_data_warehouses(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=500, ge=1, le=1000),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BASE_VIEW)),
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
# 5. 店铺列表
# ============================================================
@router.get("/shops", response_model=DataShopListOut)
async def list_data_shops(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=500, ge=1, le=1000),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BASE_VIEW)),
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
    page_size: int = Query(default=50, ge=1, le=5000),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BASE_VIEW)),
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
    keyword: str | None = Query(default=None, description="按 commodity_sku 模糊搜索"),
    enabled: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=5000),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BASE_VIEW)),
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
        if pl.commodity_sku is None:
            continue
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
# 8. sync_state 汇总(同步管理页用)
# ============================================================
@router.get("/sync-state", response_model=list[DataSyncStateRow])
async def list_sync_state(
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(SYNC_VIEW)),
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
