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
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import Float, case, func, or_, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.api.deps import (
    UserContext,
    db_session,
    db_session_readonly,
    get_current_user,
    require_permission,
)
from app.core.countries import normalize_reportable_country_code
from app.core.exceptions import ConflictError, NotFound, ValidationFailed
from app.core.permissions import (
    DATA_BASE_EDIT,
    DATA_BASE_VIEW,
    DATA_BIZ_EDIT,
    DATA_BIZ_VIEW,
    SYNC_VIEW,
)
from app.core.query import escape_like
from app.core.timezone import BEIJING, order_display_timezone, to_order_display_time
from app.models.commodity import CommodityMaster
from app.models.in_transit import InTransitItem, InTransitRecord
from app.models.inventory import InventorySnapshotLatest
from app.models.order import (
    ORDER_SOURCE_PACKAGE,
    OrderDetail,
    OrderHeader,
    OrderItem,
)
from app.models.order_info_match_import import OrderInfoMatchImportFile
from app.models.product_listing import ProductListing
from app.models.shop import Shop
from app.models.sku import SkuConfig
from app.models.sku_mapping import SkuMappingComponent
from app.models.task_run import TaskRun
from app.models.third_party_inventory import (
    ThirdPartyInventoryCurrent,
    ThirdPartyInventoryImportBatch,
    ThirdPartyInventoryImportItem,
    ThirdPartyWarehouse,
)
from app.models.warehouse import Warehouse
from app.schemas.data import (
    DataInventoryItem,
    DataInventoryListOut,
    DataInventoryWarehouseGroup,
    DataInventoryWarehouseGroupListOut,
    DataOrderDetail,
    DataOrderItem,
    DataOrderListOut,
    DataOrderPatch,
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
    OrderInfoMatchActiveTaskOut,
    OrderInfoMatchApplyOut,
    OrderInfoMatchApplyTaskOut,
    OrderInfoMatchPreviewOut,
    SkuOverviewListOut,
    ThirdPartyInventoryCurrentIn,
    ThirdPartyInventoryCurrentPatch,
    ThirdPartyInventoryImportBatchDetailOut,
    ThirdPartyInventoryImportBatchListOut,
    ThirdPartyInventoryImportBatchOut,
    ThirdPartyInventoryImportIssue,
    ThirdPartyInventoryImportItemOut,
    ThirdPartyInventoryItemOut,
    ThirdPartyInventoryPreviewOut,
    ThirdPartyInventoryWarehouseGroup,
    ThirdPartyInventoryWarehouseGroupListOut,
    ThirdPartyWarehouseIn,
    ThirdPartyWarehouseListOut,
    ThirdPartyWarehouseOut,
    ThirdPartyWarehousePatch,
)
from app.services.order_edit import (
    apply_order_info_match,
    build_order_info_match_error_report,
    build_template_workbook,
    parse_requested_fields,
    patch_order_header,
    preview_order_info_match,
)
from app.services.third_party_inventory import (
    confirm_import_batch,
    create_import_preview,
    delete_current_item,
    expire_pending_batch,
    patch_current_item,
    sync_import_items_warehouse_id,
    upsert_current_item,
)
from app.tasks.jobs.order_info_match import JOB_NAME as ORDER_INFO_MATCH_APPLY_JOB_NAME
from app.tasks.queue import enqueue_task

router = APIRouter(prefix="/api/data", tags=["data"])

SYNC_STATE_JOBS = (
    "sync_shop",
    "sync_warehouse",
    "sync_product_listing",
    "sync_inventory",
    "sync_order_list",
    "sync_out_records",
)
TASK_RUN_SYNC_STATE_JOBS = ("daily_archive", "retry_failed_api_calls")
ORDER_INFO_MATCH_DEDUPE_KEY = ORDER_INFO_MATCH_APPLY_JOB_NAME
ORDER_INFO_MATCH_FILE_TTL_HOURS = 24


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


def _apply_direction(columns: tuple[Any, ...], sort_order: str) -> list[Any]:
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
            OrderDetail.source == OrderHeader.source,
            _order_detail_visible_predicate(),
        )
        .scalar_subquery()
    )
    return case(
        ((visible_detail_exists > 0) | OrderHeader.postal_code.is_not(None), 1),
        else_=0,
    )


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


def _order_display_time_payload(header: OrderHeader) -> dict[str, object | None]:
    timezone = order_display_timezone(header.marketplace_id, header.country_code)
    return {
        "purchase_date_local": to_order_display_time(
            header.purchase_date,
            header.marketplace_id,
            header.country_code,
        ),
        "last_update_date_local": to_order_display_time(
            header.last_update_date,
            header.marketplace_id,
            header.country_code,
        ),
        "display_timezone": getattr(timezone, "key", str(timezone)),
    }


def _apply_order_sort(stmt: Any, sort_by: str | None, sort_order: str) -> Any:
    item_count_expr = _order_item_count_expr()
    has_detail_expr = _order_has_detail_expr()
    amount_expr = func.coalesce(OrderHeader.order_total_amount.cast(Float), -1.0)
    sort_map: dict[str, tuple[Any, ...]] = {
        "amazonOrderId": (OrderHeader.amazon_order_id,),
        "orderPlatform": (OrderHeader.order_platform,),
        "packageSn": (OrderHeader.package_sn,),
        "packageStatus": (OrderHeader.package_status,),
        "shopName": (
            case((OrderHeader.shop_name.is_(None), 1), else_=0),
            OrderHeader.shop_name,
        ),
        "postalCode": (
            case((OrderHeader.postal_code.is_(None), 1), else_=0),
            OrderHeader.postal_code,
        ),
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
        commodity_exists = (
            select(CommodityMaster.sku)
            .where(CommodityMaster.sku == InventorySnapshotLatest.commodity_sku)
            .exists()
        )
        listing_exists = (
            select(ProductListing.id)
            .where(ProductListing.commodity_sku == InventorySnapshotLatest.commodity_sku)
            .exists()
        )
        component_exists = (
            select(SkuMappingComponent.id)
            .where(SkuMappingComponent.inventory_sku == InventorySnapshotLatest.commodity_sku)
            .exists()
        )
        known_sku_exists = commodity_exists | listing_exists | component_exists
        stmt = stmt.where(~known_sku_exists if is_package else known_sku_exists)
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
    columns = sort_map.get(
        sort_by or "", (InTransitRecord.update_time, InTransitRecord.last_seen_at)
    )
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
    platform: str | None = Query(default=None),
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
    if platform:
        base = base.where(OrderHeader.order_platform == platform)
    if status:
        base = base.where(
            (OrderHeader.package_status == status) | (OrderHeader.order_status == status)
        )
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

    detail_set: set[tuple[str, str, str]] = set()
    if rows:
        keys = [(r.shop_id, r.amazon_order_id, r.source) for r in rows]
        # * 必须用复合键过滤。只按 shop_id IN(...) 会拉回该 shop 的全部历史 detail,
        # 在数据量大时造成内存爆炸(review H-N1)。
        det_rows = (
            await db.execute(
                select(
                    OrderDetail.shop_id,
                    OrderDetail.amazon_order_id,
                    OrderDetail.source,
                ).where(
                    tuple_(
                        OrderDetail.shop_id,
                        OrderDetail.amazon_order_id,
                        OrderDetail.source,
                    ).in_(keys),
                    _order_detail_visible_predicate(),
                )
            )
        ).all()
        detail_set = {
            (shop_id, amazon_order_id, source) for shop_id, amazon_order_id, source in det_rows
        }

    items = [
        DataOrderSummary.model_validate(
            {
                **{
                    k: getattr(r, k)
                    for k in (
                        "shop_id",
                        "amazon_order_id",
                        "order_platform",
                        "package_sn",
                        "package_status",
                        "shop_name",
                        "postal_code",
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
                "has_detail": (
                    (r.shop_id, r.amazon_order_id, r.source) in detail_set
                    or bool(getattr(r, "postal_code", None))
                ),
                "item_count": item_count_map.get(r.id, 0),
                **_order_display_time_payload(r),
            }
        )
        for r in rows
    ]
    return DataOrderListOut(items=items, total=int(total or 0), page=page, page_size=page_size)


@router.get("/order-platforms", response_model=list[str])
async def list_order_platforms(
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BIZ_VIEW)),
) -> list[str]:
    platform_expr = func.trim(OrderHeader.order_platform)
    rows = (
        await db.execute(
            select(platform_expr)
            .where(OrderHeader.order_platform.is_not(None), platform_expr != "")
            .distinct()
            .order_by(platform_expr.asc())
        )
    ).all()
    return [platform for (platform,) in rows if platform]


async def _data_order_detail_from_header(
    db: AsyncSession,
    header: OrderHeader,
) -> DataOrderDetail:
    item_rows = (
        (await db.execute(select(OrderItem).where(OrderItem.order_id == header.id))).scalars().all()
    )

    detail = (
        await db.execute(
            select(OrderDetail).where(
                (OrderDetail.shop_id == header.shop_id)
                & (OrderDetail.amazon_order_id == header.amazon_order_id)
                & (OrderDetail.source == ORDER_SOURCE_PACKAGE)
            )
        )
    ).scalar_one_or_none()

    detail_payload = {
        "postal_code": header.postal_code or (detail.postal_code if detail else None),
        "state_or_region": detail.state_or_region if detail else None,
        "city": detail.city if detail else None,
        "detail_address": detail.detail_address if detail else None,
        "receiver_name": detail.receiver_name if detail else None,
        "detail_fetched_at": detail.fetched_at if detail else None,
    }
    return DataOrderDetail.model_validate(
        {
            **{
                k: getattr(header, k)
                for k in (
                    "shop_id",
                    "amazon_order_id",
                    "order_platform",
                    "package_sn",
                    "package_status",
                    "shop_name",
                    "postal_code",
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
            **_order_display_time_payload(header),
            **detail_payload,
        }
    )


@router.get("/orders/{shop_id}/{amazon_order_id}", response_model=DataOrderDetail)
async def get_order_detail(
    shop_id: str = Path(...),
    amazon_order_id: str = Path(...),
    package_sn: str | None = Query(default=None),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BIZ_VIEW)),
) -> DataOrderDetail:
    header_stmt = select(OrderHeader).where(
        (OrderHeader.shop_id == shop_id)
        & (OrderHeader.amazon_order_id == amazon_order_id)
        & (OrderHeader.source == ORDER_SOURCE_PACKAGE)
    )
    if package_sn is not None:
        header_stmt = header_stmt.where(OrderHeader.package_sn == package_sn)
    else:
        header_stmt = header_stmt.order_by(
            OrderHeader.purchase_date.desc(), OrderHeader.id.desc()
        ).limit(1)
    header = (await db.execute(header_stmt)).scalar_one_or_none()
    if header is None:
        raise NotFound(f"订单 {shop_id}/{amazon_order_id}/{ORDER_SOURCE_PACKAGE} 不存在")

    return await _data_order_detail_from_header(db, header)


@router.patch("/orders/{shop_id}/{amazon_order_id}", response_model=DataOrderDetail)
async def patch_order_detail(
    patch: DataOrderPatch,
    shop_id: str = Path(...),
    amazon_order_id: str = Path(...),
    package_sn: str | None = Query(default=None),
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(DATA_BIZ_EDIT)),
) -> DataOrderDetail:
    header = await patch_order_header(
        db,
        shop_id=shop_id,
        amazon_order_id=amazon_order_id,
        package_sn=package_sn,
        patch=patch,
        user_id=user.id,
    )
    return await _data_order_detail_from_header(db, header)


@router.get("/order-info-match/template")
async def export_order_info_match_template(
    fields: str = Query(default=""),
    _: None = Depends(require_permission(DATA_BIZ_EDIT)),
) -> StreamingResponse:
    selected_fields = parse_requested_fields(fields)
    workbook = build_template_workbook(selected_fields)
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=order-info-match-template.xlsx"},
    )


@router.post("/order-info-match/preview", response_model=OrderInfoMatchPreviewOut)
async def preview_order_info_match_endpoint(
    request: Request,
    fields: str = Query(default=""),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BIZ_EDIT)),
) -> OrderInfoMatchPreviewOut:
    selected_fields = parse_requested_fields(fields)
    content = await request.body()
    return await preview_order_info_match(db, fields=selected_fields, content=content)


async def _get_active_order_info_match_task(db: AsyncSession) -> TaskRun | None:
    return (
        await db.execute(
            select(TaskRun)
            .where(
                TaskRun.job_name == ORDER_INFO_MATCH_APPLY_JOB_NAME,
                TaskRun.status.in_(("pending", "running")),
            )
            .order_by(TaskRun.created_at.desc(), TaskRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


@router.post("/order-info-match/apply-task", response_model=OrderInfoMatchApplyTaskOut)
async def create_order_info_match_apply_task_endpoint(
    request: Request,
    fields: str = Query(default=""),
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(DATA_BIZ_EDIT)),
) -> OrderInfoMatchApplyTaskOut:
    selected_fields = parse_requested_fields(fields)
    active = await _get_active_order_info_match_task(db)
    if active is not None:
        return OrderInfoMatchApplyTaskOut(task_id=active.id, existing=True)

    content = await request.body()
    if not content:
        raise ValidationFailed("导入文件没有有效数据")

    filename = unquote(request.headers.get("x-filename") or "order-info-match.xlsx")[:255]
    now = datetime.now(tz=BEIJING)
    import_file = OrderInfoMatchImportFile(
        filename=filename,
        content=content,
        fields=[field.key for field in selected_fields],
        created_by=user.id,
        expires_at=now + timedelta(hours=ORDER_INFO_MATCH_FILE_TTL_HOURS),
    )
    db.add(import_file)
    await db.flush()
    task_id, existing = await enqueue_task(
        db,
        job_name=ORDER_INFO_MATCH_APPLY_JOB_NAME,
        trigger_source="manual",
        dedupe_key=ORDER_INFO_MATCH_DEDUPE_KEY,
        payload={"file_id": import_file.id, "user_id": user.id},
    )
    if not existing:
        import_file.task_id = task_id
        await db.commit()
    return OrderInfoMatchApplyTaskOut(task_id=task_id, existing=existing)


@router.get("/order-info-match/apply-task/active", response_model=OrderInfoMatchActiveTaskOut)
async def get_active_order_info_match_apply_task_endpoint(
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BIZ_EDIT)),
) -> OrderInfoMatchActiveTaskOut:
    active = await _get_active_order_info_match_task(db)
    return OrderInfoMatchActiveTaskOut(task_id=active.id if active is not None else None)


@router.post("/order-info-match/apply", response_model=OrderInfoMatchApplyOut)
async def apply_order_info_match_endpoint(
    request: Request,
    fields: str = Query(default=""),
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(DATA_BIZ_EDIT)),
) -> OrderInfoMatchApplyOut:
    selected_fields = parse_requested_fields(fields)
    content = await request.body()
    return await apply_order_info_match(
        db,
        fields=selected_fields,
        content=content,
        user_id=user.id,
    )


@router.post("/order-info-match/error-report")
async def download_order_info_match_error_report_endpoint(
    request: Request,
    fields: str = Query(default=""),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BIZ_EDIT)),
) -> StreamingResponse:
    selected_fields = parse_requested_fields(fields)
    content = await request.body()
    workbook = await build_order_info_match_error_report(db, fields=selected_fields, content=content)
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=order-info-match-error-report.xlsx"},
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
        commodity_rows = (
            await db.execute(
                select(
                    CommodityMaster.sku,
                    CommodityMaster.name,
                    CommodityMaster.img_url,
                ).where(CommodityMaster.sku.in_(sku_codes))
            )
        ).all()
        for sku, name, img in commodity_rows:
            matched_skus.add(sku)
            name_map[sku] = (name, img)
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
        component_skus = (
            (
                await db.execute(
                    select(SkuMappingComponent.inventory_sku).where(
                        SkuMappingComponent.inventory_sku.in_(sku_codes)
                    )
                )
            )
            .scalars()
            .all()
        )
        matched_skus.update(component_skus)

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
        .order_by(
            Warehouse.name.asc(),
            InventorySnapshotLatest.warehouse_id.asc(),
            InventorySnapshotLatest.commodity_sku.asc(),
        )
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
        commodity_rows = (
            await db.execute(
                select(
                    CommodityMaster.sku,
                    CommodityMaster.name,
                    CommodityMaster.img_url,
                ).where(CommodityMaster.sku.in_(sku_codes))
            )
        ).all()
        for sku, name, img in commodity_rows:
            matched_skus.add(sku)
            name_map[sku] = (name, img)
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
        component_skus = (
            (
                await db.execute(
                    select(SkuMappingComponent.inventory_sku).where(
                        SkuMappingComponent.inventory_sku.in_(sku_codes)
                    )
                )
            )
            .scalars()
            .all()
        )
        matched_skus.update(component_skus)

    items_by_warehouse: dict[str, list[DataInventoryItem]] = {
        warehouse_id: [] for warehouse_id in warehouse_ids
    }
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
def _normalize_third_party_country(country: str | None) -> str | None:
    if country is None:
        return None
    normalized = normalize_reportable_country_code(country)
    if normalized is None:
        raise ValidationFailed("国家代码无效")
    return normalized


def _third_party_batch_out(batch: ThirdPartyInventoryImportBatch) -> ThirdPartyInventoryImportBatchOut:
    summary = batch.summary or {}
    unmaintained = summary.get("unmaintained_warehouses") or []
    return ThirdPartyInventoryImportBatchOut.model_validate(
        {
            "id": batch.id,
            "filename": batch.filename,
            "status": batch.status,
            "row_count": batch.row_count,
            "valid_row_count": batch.valid_row_count,
            "skipped_row_count": batch.skipped_row_count,
            "new_warehouse_count": batch.new_warehouse_count,
            "unmaintained_warehouse_count": (
                len(unmaintained) if isinstance(unmaintained, list) else 0
            ),
            "created_by": batch.created_by,
            "confirmed_by": batch.confirmed_by,
            "created_at": batch.created_at,
            "confirmed_at": batch.confirmed_at,
            "summary": summary,
        }
    )


def _third_party_preview_out(batch: ThirdPartyInventoryImportBatch) -> ThirdPartyInventoryPreviewOut:
    summary = batch.summary or {}
    issues = [
        ThirdPartyInventoryImportIssue.model_validate(issue)
        for issue in summary.get("issues", [])
        if isinstance(issue, dict)
    ]
    payload = _third_party_batch_out(batch).model_dump()
    payload.update(
        {
            "new_warehouses": summary.get("new_warehouses") or [],
            "unmaintained_warehouses": summary.get("unmaintained_warehouses") or [],
            "issues": issues,
        }
    )
    return ThirdPartyInventoryPreviewOut.model_validate(payload)


def _third_party_inventory_item_out(
    item: ThirdPartyInventoryCurrent,
    warehouse_name: str,
    country: str | None,
) -> ThirdPartyInventoryItemOut:
    return ThirdPartyInventoryItemOut.model_validate(
        {
            "id": item.id,
            "warehouse_id": item.warehouse_id,
            "warehouse_name": warehouse_name,
            "country": country,
            "participates": country is not None,
            "commodity_sku": item.commodity_sku,
            "available": item.available,
            "reserved": item.reserved,
            "source_batch_id": item.source_batch_id,
            "last_operation": item.last_operation,
            "updated_at": item.updated_at,
        }
    )


@router.get("/third-party-warehouses", response_model=ThirdPartyWarehouseListOut)
async def list_third_party_warehouses(
    keyword: str | None = Query(default=None),
    country: str | None = Query(default=None),
    only_missing_country: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BASE_VIEW)),
) -> ThirdPartyWarehouseListOut:
    current_subquery = (
        select(
            ThirdPartyInventoryCurrent.warehouse_id.label("warehouse_id"),
            func.count(ThirdPartyInventoryCurrent.id).label("sku_count"),
            func.coalesce(func.sum(ThirdPartyInventoryCurrent.available), 0).label(
                "total_available"
            ),
            func.coalesce(func.sum(ThirdPartyInventoryCurrent.reserved), 0).label(
                "total_reserved"
            ),
        )
        .group_by(ThirdPartyInventoryCurrent.warehouse_id)
        .subquery()
    )
    import_subquery = (
        select(
            ThirdPartyInventoryImportItem.warehouse_id.label("warehouse_id"),
            func.count(ThirdPartyInventoryImportItem.id).label("import_item_count"),
        )
        .where(ThirdPartyInventoryImportItem.warehouse_id.is_not(None))
        .group_by(ThirdPartyInventoryImportItem.warehouse_id)
        .subquery()
    )
    base = (
        select(
            ThirdPartyWarehouse,
            func.coalesce(current_subquery.c.sku_count, 0).label("sku_count"),
            func.coalesce(current_subquery.c.total_available, 0).label("total_available"),
            func.coalesce(current_subquery.c.total_reserved, 0).label("total_reserved"),
            func.coalesce(import_subquery.c.import_item_count, 0).label("import_item_count"),
        )
        .outerjoin(current_subquery, current_subquery.c.warehouse_id == ThirdPartyWarehouse.id)
        .outerjoin(import_subquery, import_subquery.c.warehouse_id == ThirdPartyWarehouse.id)
    )
    if keyword:
        base = base.where(ThirdPartyWarehouse.name.ilike(f"%{escape_like(keyword)}%", escape="\\"))
    if country:
        base = base.where(ThirdPartyWarehouse.country == country.upper())
    if only_missing_country:
        base = base.where(ThirdPartyWarehouse.country.is_(None))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(
            base.order_by(ThirdPartyWarehouse.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = [
        ThirdPartyWarehouseOut.model_validate(
            {
                "id": warehouse.id,
                "name": warehouse.name,
                "country": warehouse.country,
                "current_sku_count": int(sku_count or 0),
                "current_total_available": int(total_available or 0),
                "current_total_reserved": int(total_reserved or 0),
                "import_item_count": int(import_item_count or 0),
                "created_at": warehouse.created_at,
                "updated_at": warehouse.updated_at,
            }
        )
        for warehouse, sku_count, total_available, total_reserved, import_item_count in rows
    ]
    return ThirdPartyWarehouseListOut(
        items=items, total=int(total or 0), page=page, page_size=page_size
    )


@router.post("/third-party-warehouses", response_model=ThirdPartyWarehouseOut)
async def create_third_party_warehouse(
    body: ThirdPartyWarehouseIn,
    db: AsyncSession = Depends(db_session),
    _: None = Depends(require_permission(DATA_BASE_EDIT)),
) -> ThirdPartyWarehouseOut:
    warehouse = ThirdPartyWarehouse(
        name=body.name,
        country=_normalize_third_party_country(body.country),
    )
    db.add(warehouse)
    try:
        await db.flush()
        await sync_import_items_warehouse_id(db, warehouse)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("三方仓名称已存在") from exc
    await db.refresh(warehouse)
    return ThirdPartyWarehouseOut.model_validate(
        {
            "id": warehouse.id,
            "name": warehouse.name,
            "country": warehouse.country,
            "created_at": warehouse.created_at,
            "updated_at": warehouse.updated_at,
        }
    )


@router.patch("/third-party-warehouses/{warehouse_id}", response_model=ThirdPartyWarehouseOut)
async def patch_third_party_warehouse(
    body: ThirdPartyWarehousePatch,
    warehouse_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: None = Depends(require_permission(DATA_BASE_EDIT)),
) -> ThirdPartyWarehouseOut:
    warehouse = (
        await db.execute(select(ThirdPartyWarehouse).where(ThirdPartyWarehouse.id == warehouse_id))
    ).scalar_one_or_none()
    if warehouse is None:
        raise NotFound("三方仓不存在")
    if body.name is not None:
        warehouse.name = body.name
    if "country" in body.model_fields_set:
        warehouse.country = _normalize_third_party_country(body.country)
    try:
        await sync_import_items_warehouse_id(db, warehouse)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("三方仓名称已存在") from exc
    await db.refresh(warehouse)
    return ThirdPartyWarehouseOut.model_validate(
        {
            "id": warehouse.id,
            "name": warehouse.name,
            "country": warehouse.country,
            "created_at": warehouse.created_at,
            "updated_at": warehouse.updated_at,
        }
    )


@router.delete("/third-party-warehouses/{warehouse_id}", status_code=204)
async def delete_third_party_warehouse(
    warehouse_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: None = Depends(require_permission(DATA_BASE_EDIT)),
) -> None:
    current_count = (
        await db.execute(
            select(func.count()).where(ThirdPartyInventoryCurrent.warehouse_id == warehouse_id)
        )
    ).scalar_one()
    history_count = (
        await db.execute(
            select(func.count()).where(ThirdPartyInventoryImportItem.warehouse_id == warehouse_id)
        )
    ).scalar_one()
    if current_count or history_count:
        raise ConflictError("三方仓存在当前库存或导入历史，不能删除")
    warehouse = (
        await db.execute(select(ThirdPartyWarehouse).where(ThirdPartyWarehouse.id == warehouse_id))
    ).scalar_one_or_none()
    if warehouse is None:
        raise NotFound("三方仓不存在")
    await db.delete(warehouse)
    await db.commit()


@router.post("/third-party-inventory/import/preview", response_model=ThirdPartyInventoryPreviewOut)
async def preview_third_party_inventory_import(
    request: Request,
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(DATA_BIZ_EDIT)),
) -> ThirdPartyInventoryPreviewOut:
    filename = unquote(request.headers.get("x-filename", "third-party-inventory.xlsx"))
    batch = await create_import_preview(
        db,
        filename=filename,
        content=await request.body(),
        created_by=user.username,
    )
    return _third_party_preview_out(batch)


@router.post(
    "/third-party-inventory/import/{batch_id}/confirm",
    response_model=ThirdPartyInventoryImportBatchOut,
)
async def confirm_third_party_inventory_import(
    batch_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(DATA_BIZ_EDIT)),
) -> ThirdPartyInventoryImportBatchOut:
    return _third_party_batch_out(
        await confirm_import_batch(db, batch_id=batch_id, confirmed_by=user.username)
    )


@router.post(
    "/third-party-inventory/import/{batch_id}/cancel",
    response_model=ThirdPartyInventoryImportBatchOut,
)
async def cancel_third_party_inventory_import(
    batch_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: None = Depends(require_permission(DATA_BIZ_EDIT)),
) -> ThirdPartyInventoryImportBatchOut:
    return _third_party_batch_out(await expire_pending_batch(db, batch_id))


@router.get("/third-party-inventory/batches", response_model=ThirdPartyInventoryImportBatchListOut)
async def list_third_party_inventory_batches(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BIZ_VIEW)),
) -> ThirdPartyInventoryImportBatchListOut:
    base = select(ThirdPartyInventoryImportBatch).order_by(
        ThirdPartyInventoryImportBatch.created_at.desc(),
        ThirdPartyInventoryImportBatch.id.desc(),
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return ThirdPartyInventoryImportBatchListOut(
        items=[_third_party_batch_out(row) for row in rows],
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )


@router.get(
    "/third-party-inventory/batches/{batch_id}",
    response_model=ThirdPartyInventoryImportBatchDetailOut,
)
async def get_third_party_inventory_batch(
    batch_id: int = Path(..., ge=1),
    only_errors: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BIZ_VIEW)),
) -> ThirdPartyInventoryImportBatchDetailOut:
    batch = (
        await db.execute(
            select(ThirdPartyInventoryImportBatch).where(
                ThirdPartyInventoryImportBatch.id == batch_id
            )
        )
    ).scalar_one_or_none()
    if batch is None:
        raise NotFound("导入批次不存在")
    item_base = select(ThirdPartyInventoryImportItem).where(
        ThirdPartyInventoryImportItem.batch_id == batch_id
    )
    if only_errors:
        item_base = item_base.where(ThirdPartyInventoryImportItem.error_message.is_not(None))
    item_total = (
        await db.execute(select(func.count()).select_from(item_base.subquery()))
    ).scalar_one()
    rows = (
        await db.execute(
            item_base.order_by(ThirdPartyInventoryImportItem.source_row_no.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    payload = _third_party_batch_out(batch).model_dump()
    payload.update(
        {
            "items": [ThirdPartyInventoryImportItemOut.model_validate(row) for row in rows],
            "item_total": int(item_total or 0),
        }
    )
    return ThirdPartyInventoryImportBatchDetailOut.model_validate(payload)


def _apply_third_party_inventory_filters(
    stmt: Any,
    *,
    warehouse_keyword: str | None,
    sku: str | None,
    country: str | None,
    only_missing_country: bool,
    only_participating: bool | None,
    only_nonzero: bool,
) -> Any:
    if warehouse_keyword:
        stmt = stmt.where(
            ThirdPartyWarehouse.name.ilike(f"%{escape_like(warehouse_keyword)}%", escape="\\")
        )
    if sku:
        stmt = stmt.where(
            ThirdPartyInventoryCurrent.commodity_sku.ilike(
                f"%{escape_like(sku)}%", escape="\\"
            )
        )
    if country:
        stmt = stmt.where(ThirdPartyWarehouse.country == country.upper())
    if only_missing_country:
        stmt = stmt.where(ThirdPartyWarehouse.country.is_(None))
    if only_participating is not None:
        stmt = stmt.where(
            ThirdPartyWarehouse.country.is_not(None)
            if only_participating
            else ThirdPartyWarehouse.country.is_(None)
        )
    if only_nonzero:
        stmt = stmt.where(
            (ThirdPartyInventoryCurrent.available > 0)
            | (ThirdPartyInventoryCurrent.reserved > 0)
        )
    return stmt


@router.get(
    "/third-party-inventory/warehouse-groups",
    response_model=ThirdPartyInventoryWarehouseGroupListOut,
)
async def list_third_party_inventory_warehouse_groups(
    warehouse_keyword: str | None = Query(default=None),
    sku: str | None = Query(default=None),
    country: str | None = Query(default=None),
    only_missing_country: bool = Query(default=False),
    only_participating: bool | None = Query(default=None),
    only_nonzero: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BIZ_VIEW)),
) -> ThirdPartyInventoryWarehouseGroupListOut:
    group_stmt = (
        select(
            ThirdPartyInventoryCurrent.warehouse_id.label("warehouse_id"),
            ThirdPartyWarehouse.name.label("warehouse_name"),
            ThirdPartyWarehouse.country.label("country"),
            func.count(ThirdPartyInventoryCurrent.id).label("sku_count"),
            func.coalesce(func.sum(ThirdPartyInventoryCurrent.available), 0).label(
                "total_available"
            ),
            func.coalesce(func.sum(ThirdPartyInventoryCurrent.reserved), 0).label(
                "total_reserved"
            ),
        )
        .join(ThirdPartyWarehouse, ThirdPartyWarehouse.id == ThirdPartyInventoryCurrent.warehouse_id)
        .group_by(
            ThirdPartyInventoryCurrent.warehouse_id,
            ThirdPartyWarehouse.name,
            ThirdPartyWarehouse.country,
        )
        .order_by(ThirdPartyWarehouse.name.asc(), ThirdPartyInventoryCurrent.warehouse_id.asc())
    )
    group_stmt = _apply_third_party_inventory_filters(
        group_stmt,
        warehouse_keyword=warehouse_keyword,
        sku=sku,
        country=country,
        only_missing_country=only_missing_country,
        only_participating=only_participating,
        only_nonzero=only_nonzero,
    )
    total = (
        await db.execute(select(func.count()).select_from(group_stmt.order_by(None).subquery()))
    ).scalar_one()
    group_rows = (
        await db.execute(group_stmt.offset((page - 1) * page_size).limit(page_size))
    ).all()
    warehouse_ids = [row.warehouse_id for row in group_rows]
    if not warehouse_ids:
        return ThirdPartyInventoryWarehouseGroupListOut(
            items=[], total=int(total or 0), page=page, page_size=page_size
        )

    item_stmt = (
        select(ThirdPartyInventoryCurrent, ThirdPartyWarehouse.name, ThirdPartyWarehouse.country)
        .join(ThirdPartyWarehouse, ThirdPartyWarehouse.id == ThirdPartyInventoryCurrent.warehouse_id)
        .where(ThirdPartyInventoryCurrent.warehouse_id.in_(warehouse_ids))
        .order_by(ThirdPartyWarehouse.name.asc(), ThirdPartyInventoryCurrent.commodity_sku.asc())
    )
    item_stmt = _apply_third_party_inventory_filters(
        item_stmt,
        warehouse_keyword=warehouse_keyword,
        sku=sku,
        country=country,
        only_missing_country=only_missing_country,
        only_participating=only_participating,
        only_nonzero=only_nonzero,
    )
    item_rows = (await db.execute(item_stmt)).all()
    items_by_warehouse: dict[int, list[ThirdPartyInventoryItemOut]] = {
        warehouse_id: [] for warehouse_id in warehouse_ids
    }
    for item, warehouse_name, row_country in item_rows:
        items_by_warehouse.setdefault(item.warehouse_id, []).append(
            _third_party_inventory_item_out(item, warehouse_name, row_country)
        )

    groups = [
        ThirdPartyInventoryWarehouseGroup.model_validate(
            {
                "warehouse_id": row.warehouse_id,
                "warehouse_name": row.warehouse_name,
                "country": row.country,
                "participates": row.country is not None,
                "sku_count": int(row.sku_count or 0),
                "total_available": int(row.total_available or 0),
                "total_reserved": int(row.total_reserved or 0),
                "items": items_by_warehouse.get(row.warehouse_id, []),
            }
        )
        for row in group_rows
    ]
    return ThirdPartyInventoryWarehouseGroupListOut(
        items=groups, total=int(total or 0), page=page, page_size=page_size
    )


@router.post("/third-party-inventory/items", response_model=ThirdPartyInventoryItemOut)
async def create_third_party_inventory_item(
    body: ThirdPartyInventoryCurrentIn,
    db: AsyncSession = Depends(db_session),
    _: None = Depends(require_permission(DATA_BIZ_EDIT)),
) -> ThirdPartyInventoryItemOut:
    item = await upsert_current_item(
        db,
        warehouse_id=body.warehouse_id,
        commodity_sku=body.commodity_sku,
        available=body.available,
        reserved=body.reserved,
    )
    warehouse = (
        await db.execute(select(ThirdPartyWarehouse).where(ThirdPartyWarehouse.id == item.warehouse_id))
    ).scalar_one()
    return _third_party_inventory_item_out(item, warehouse.name, warehouse.country)


@router.patch("/third-party-inventory/items/{item_id}", response_model=ThirdPartyInventoryItemOut)
async def update_third_party_inventory_item(
    body: ThirdPartyInventoryCurrentPatch,
    item_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: None = Depends(require_permission(DATA_BIZ_EDIT)),
) -> ThirdPartyInventoryItemOut:
    item = await patch_current_item(
        db,
        item_id=item_id,
        values=body.model_dump(exclude_unset=True),
    )
    warehouse = (
        await db.execute(select(ThirdPartyWarehouse).where(ThirdPartyWarehouse.id == item.warehouse_id))
    ).scalar_one()
    return _third_party_inventory_item_out(item, warehouse.name, warehouse.country)


@router.delete("/third-party-inventory/items/{item_id}", status_code=204)
async def remove_third_party_inventory_item(
    item_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(db_session),
    _: None = Depends(require_permission(DATA_BIZ_EDIT)),
) -> None:
    await delete_current_item(db, item_id)


@router.get("/shops", response_model=DataShopListOut)
async def list_data_shops(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=500, ge=1, le=1000),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BASE_VIEW)),
) -> DataShopListOut:
    total = (await db.execute(select(func.count()).select_from(Shop))).scalar_one()
    rows = (
        (
            await db.execute(
                select(Shop)
                .order_by(Shop.marketplace_id, Shop.id)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        )
        .scalars()
        .all()
    )
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
    is_group: bool | None = Query(default=None, description="按 SKU 类型过滤：true=组合 SKU，false=单品 SKU"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=5000),
    db: AsyncSession = Depends(db_session_readonly),
    _: None = Depends(require_permission(DATA_BASE_VIEW)),
) -> SkuOverviewListOut:
    """Return SKU-level overview: config + aggregated listings, paginated by SKU."""
    from app.schemas.data import SkuListingItem, SkuOverviewItem

    base = (
        select(SkuConfig, CommodityMaster)
        .outerjoin(CommodityMaster, CommodityMaster.sku == SkuConfig.commodity_sku)
        .order_by(SkuConfig.commodity_sku)
    )
    if enabled is not None:
        base = base.where(SkuConfig.enabled.is_(enabled))
    if is_group is not None:
        base = base.where(CommodityMaster.is_group.is_(is_group))
    if keyword:
        keyword_like = f"%{escape_like(keyword)}%"
        base = base.where(
            or_(
                SkuConfig.commodity_sku.ilike(keyword_like, escape="\\"),
                CommodityMaster.name.ilike(keyword_like, escape="\\"),
            )
        )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    sku_rows = (await db.execute(base.offset((page - 1) * page_size).limit(page_size))).all()

    if not sku_rows:
        return SkuOverviewListOut(items=[], total=int(total or 0), page=page, page_size=page_size)

    sku_codes = [r[0].commodity_sku for r in sku_rows]

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
    for sku_cfg, commodity in sku_rows:
        sku = sku_cfg.commodity_sku
        sku_listings = listings_by_sku.get(sku, [])
        name = commodity.name if commodity is not None else None
        image = commodity.img_url if commodity is not None else None
        if name is None and sku_listings:
            name = sku_listings[0].commodity_name
        if image is None and sku_listings:
            image = sku_listings[0].main_image
        total_day30 = sum((pl.day30_sale_num or 0) for pl in sku_listings)

        items.append(
            SkuOverviewItem(
                commodity_sku=sku,
                commodity_id=commodity.commodity_id if commodity is not None else None,
                commodity_name=name,
                main_image=image,
                state=commodity.state if commodity is not None else None,
                is_group=commodity.is_group if commodity is not None else None,
                purchase_days=commodity.purchase_days if commodity is not None else None,
                has_listing=bool(sku_listings),
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
    from app.models.task_run import TaskRun

    rows = (
        (
            await db.execute(
                select(SyncState)
                .where(SyncState.job_name.in_(SYNC_STATE_JOBS))
                .order_by(SyncState.job_name)
            )
        )
        .scalars()
        .all()
    )
    sync_rows = [
        DataSyncStateRow(
            job_name=r.job_name,
            last_run_at=r.last_run_at,
            last_success_at=r.last_success_at,
            last_status=r.last_status,
            last_error=r.last_error,
        )
        for r in rows
        if r.job_name in SYNC_STATE_JOBS
    ]

    task_rows: list[DataSyncStateRow] = []
    for job_name in TASK_RUN_SYNC_STATE_JOBS:
        latest = (
            await db.execute(
                select(TaskRun)
                .where(TaskRun.job_name == job_name)
                .order_by(TaskRun.created_at.desc(), TaskRun.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        latest_success = (
            await db.execute(
                select(TaskRun)
                .where(TaskRun.job_name == job_name, TaskRun.status == "success")
                .order_by(TaskRun.finished_at.desc(), TaskRun.created_at.desc(), TaskRun.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        task_rows.append(
            DataSyncStateRow(
                job_name=job_name,
                last_run_at=(latest.started_at or latest.created_at) if latest else None,
                last_success_at=latest_success.finished_at if latest_success else None,
                last_status=latest.status if latest else None,
                last_error=latest.error_msg if latest and latest.status == "failed" else None,
            )
        )

    return [*sync_rows, *task_rows]
