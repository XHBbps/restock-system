"""外部数据源观测 DTO。

设计要点:
- 字段内部使用 snake_case(与 ORM 一致),自动通过 alias_generator 输出 camelCase
- `from_attributes=True` + `populate_by_name=True`:既支持 `Model.model_validate(orm_obj)`,
  也允许外部构造时使用 snake_case 或 camelCase 字段名
- 输出 JSON 遵循 `by_alias=True` 语义(FastAPI 默认会使用 alias 序列化)

字段命名保持与赛狐接口返回结构一致,便于操作员对照核查。
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class SaihuLikeModel(BaseModel):
    """所有 data DTO 基类。

    使用 `alias_generator=to_camel` 自动把 snake_case 字段名转为 camelCase 别名。
    FastAPI 序列化时会优先使用 alias,因此输出 JSON 字段是 camelCase。
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )


# ==================== 订单列表 ====================
class DataOrderItem(SaihuLikeModel):
    order_item_id: str
    commodity_sku: str
    seller_sku: str | None = None
    quantity_ordered: int
    quantity_shipped: int
    quantity_unfulfillable: int
    refund_num: int
    item_price_currency: str | None = None
    item_price_amount: Decimal | None = None


class DataOrderSummary(SaihuLikeModel):
    shop_id: str
    amazon_order_id: str
    marketplace_id: str
    country_code: str
    order_status: str
    order_total_currency: str | None = None
    order_total_amount: Decimal | None = None
    fulfillment_channel: str | None = None
    purchase_date: datetime
    last_update_date: datetime
    refund_status: str | None = None
    last_sync_at: datetime
    has_detail: bool = False
    item_count: int = 0


class DataOrderListOut(BaseModel):
    items: list[DataOrderSummary]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class DataOrderDetail(SaihuLikeModel):
    """订单完整信息(header + items + postcode detail)。"""

    shop_id: str
    amazon_order_id: str
    marketplace_id: str
    country_code: str
    order_status: str
    order_total_currency: str | None = None
    order_total_amount: Decimal | None = None
    fulfillment_channel: str | None = None
    purchase_date: datetime
    last_update_date: datetime
    refund_status: str | None = None
    is_buyer_requested_cancel: bool
    last_sync_at: datetime
    items: list[DataOrderItem]
    postal_code: str | None = None
    state_or_region: str | None = None
    city: str | None = None
    detail_address: str | None = None
    receiver_name: str | None = None
    detail_fetched_at: datetime | None = None


# ==================== 库存明细 ====================
class DataInventoryItem(SaihuLikeModel):
    commodity_sku: str
    commodity_name: str | None = None
    main_image: str | None = None
    is_package: bool
    warehouse_id: str
    warehouse_name: str
    warehouse_type: int
    country: str | None = None
    stock_available: int
    stock_occupy: int
    updated_at: datetime


class DataInventoryListOut(BaseModel):
    items: list[DataInventoryItem]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class DataInventoryWarehouseGroup(SaihuLikeModel):
    warehouse_id: str
    warehouse_name: str
    warehouse_type: int
    sku_count: int
    total_available: int
    total_occupy: int
    items: list[DataInventoryItem]


class DataInventoryWarehouseGroupListOut(BaseModel):
    items: list[DataInventoryWarehouseGroup]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ==================== 其他出库列表 ====================
class DataOutRecordItem(SaihuLikeModel):
    commodity_id: str | None = None
    commodity_sku: str
    goods: int
    per_purchase: Decimal | None = None


class DataOutRecord(SaihuLikeModel):
    saihu_out_record_id: str
    warehouse_id: str | None = None
    out_warehouse_no: str | None = None
    target_warehouse_id: str | None = None
    target_warehouse_name: str | None = None
    target_country: str | None = None
    update_time: datetime | None = None
    type: int | None = None
    type_name: str | None = None
    remark: str | None = None
    status: str | None = None
    is_in_transit: bool
    last_seen_at: datetime
    items: list[DataOutRecordItem]


class DataOutRecordListOut(BaseModel):
    items: list[DataOutRecord]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ==================== 仓库列表 ====================
class DataWarehouse(SaihuLikeModel):
    id: str
    name: str
    type: int
    country: str | None = None
    replenish_site: str | None = None
    total_stock: int = 0
    last_sync_at: datetime


class DataWarehouseListOut(BaseModel):
    items: list[DataWarehouse]
    total: int
    page: int = 1
    page_size: int = 500

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ==================== 店铺列表 ====================
class DataShop(SaihuLikeModel):
    id: str
    name: str
    seller_id: str | None = None
    region: str | None = None
    marketplace_id: str | None = None
    status: str
    ad_status: str | None = None
    sync_enabled: bool
    last_sync_at: datetime | None = None


class DataShopListOut(BaseModel):
    items: list[DataShop]
    total: int
    page: int = 1
    page_size: int = 500

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ==================== 在线产品信息 ====================
class DataProductListing(SaihuLikeModel):
    id: int
    commodity_sku: str | None = None
    commodity_id: str | None = None
    commodity_name: str | None = None
    main_image: str | None = None
    shop_id: str
    marketplace_id: str
    seller_sku: str | None = None
    parent_sku: str | None = None
    day7_sale_num: int | None = None
    day14_sale_num: int | None = None
    day30_sale_num: int | None = None
    is_matched: bool
    online_status: str
    last_sync_at: datetime


class DataProductListingListOut(BaseModel):
    items: list[DataProductListing]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ==================== sync_state ====================
class DataSyncStateRow(BaseModel):
    job_name: str
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None


# ==================== SKU Overview (grouped) ====================
class SkuListingItem(BaseModel):
    """Single marketplace listing under a SKU."""

    id: int
    shop_id: str
    marketplace_id: str
    seller_sku: str | None = None
    day7_sale_num: int | None = None
    day14_sale_num: int | None = None
    day30_sale_num: int | None = None
    online_status: str
    last_sync_at: str | None = None

    model_config = {"from_attributes": True}


class SkuOverviewItem(BaseModel):
    """SKU-level row with config + aggregated listing info."""

    commodity_sku: str
    commodity_name: str | None = None
    main_image: str | None = None
    enabled: bool
    lead_time_days: int | None = None
    listing_count: int
    total_day30_sales: int
    listings: list[SkuListingItem]


class SkuOverviewListOut(BaseModel):
    items: list[SkuOverviewItem]
    total: int
    page: int
    page_size: int
