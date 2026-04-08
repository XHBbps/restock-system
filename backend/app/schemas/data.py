"""外部数据源观测 DTO。

字段命名与赛狐接口返回结构基本一致（camelCase 别名），
让采购员能直接对照"赛狐原始返回 ↔ 本系统入库后的数据"。
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


# ==================== 公用分页包装 ====================
class PaginatedOut(BaseModel):
    items: list[Any]
    total: int
    page: int
    pageSize: int


class SaihuLikeModel(BaseModel):
    """所有 data DTO 基类，使用 camelCase 字段别名对外输出。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ==================== 订单列表 ====================
class DataOrderItem(SaihuLikeModel):
    orderItemId: str
    commoditySku: str
    sellerSku: str | None = None
    quantityOrdered: int
    quantityShipped: int
    quantityUnfulfillable: int
    refundNum: int
    itemPriceCurrency: str | None = None
    itemPriceAmount: Decimal | None = None


class DataOrderSummary(SaihuLikeModel):
    shopId: str
    amazonOrderId: str
    marketplaceId: str
    countryCode: str
    orderStatus: str
    orderTotalCurrency: str | None = None
    orderTotalAmount: Decimal | None = None
    fulfillmentChannel: str | None = None
    purchaseDate: datetime
    lastUpdateDate: datetime
    refundStatus: str | None = None
    lastSyncAt: datetime
    hasDetail: bool = False
    itemCount: int = 0


class DataOrderListOut(BaseModel):
    items: list[DataOrderSummary]
    total: int
    page: int
    pageSize: int


class DataOrderDetail(SaihuLikeModel):
    """订单完整信息（header + items + postcode detail）。"""

    # header
    shopId: str
    amazonOrderId: str
    marketplaceId: str
    countryCode: str
    orderStatus: str
    orderTotalCurrency: str | None = None
    orderTotalAmount: Decimal | None = None
    fulfillmentChannel: str | None = None
    purchaseDate: datetime
    lastUpdateDate: datetime
    refundStatus: str | None = None
    isBuyerRequestedCancel: bool
    lastSyncAt: datetime
    # items
    items: list[DataOrderItem]
    # order_detail (可能为 None，表示尚未拉详情)
    postalCode: str | None = None
    stateOrRegion: str | None = None
    city: str | None = None
    detailAddress: str | None = None
    receiverName: str | None = None
    detailFetchedAt: datetime | None = None


# ==================== 库存明细 ====================
class DataInventoryItem(SaihuLikeModel):
    commoditySku: str
    commodityName: str | None = None
    mainImage: str | None = None
    warehouseId: str
    warehouseName: str
    warehouseType: int
    country: str | None = None
    stockAvailable: int
    stockOccupy: int
    updatedAt: datetime


class DataInventoryListOut(BaseModel):
    items: list[DataInventoryItem]
    total: int
    page: int
    pageSize: int


# ==================== 其他出库列表 ====================
class DataOutRecordItem(SaihuLikeModel):
    commoditySku: str
    goods: int  # 在途数


class DataOutRecord(SaihuLikeModel):
    saihuOutRecordId: str
    outWarehouseNo: str | None = None
    targetWarehouseId: str | None = None
    targetWarehouseName: str | None = None
    targetCountry: str | None = None
    remark: str | None = None
    status: str | None = None
    isInTransit: bool
    lastSeenAt: datetime
    items: list[DataOutRecordItem]


class DataOutRecordListOut(BaseModel):
    items: list[DataOutRecord]
    total: int
    page: int
    pageSize: int


# ==================== 仓库列表 ====================
class DataWarehouse(SaihuLikeModel):
    id: str
    name: str
    type: int
    country: str | None = None
    replenishSite: str | None = None
    lastSyncAt: datetime


class DataWarehouseListOut(BaseModel):
    items: list[DataWarehouse]
    total: int


# ==================== 店铺列表 ====================
class DataShop(SaihuLikeModel):
    id: str
    name: str
    sellerId: str | None = None
    region: str | None = None
    marketplaceId: str | None = None
    status: str
    adStatus: str | None = None
    syncEnabled: bool
    lastSyncAt: datetime | None = None


class DataShopListOut(BaseModel):
    items: list[DataShop]
    total: int


# ==================== 在线产品信息 ====================
class DataProductListing(SaihuLikeModel):
    id: int
    commoditySku: str
    commodityId: str
    commodityName: str | None = None
    mainImage: str | None = None
    shopId: str
    marketplaceId: str
    sellerSku: str | None = None
    parentSku: str | None = None
    day7SaleNum: int | None = None
    day14SaleNum: int | None = None
    day30SaleNum: int | None = None
    isMatched: bool
    onlineStatus: str
    lastSyncAt: datetime


class DataProductListingListOut(BaseModel):
    items: list[DataProductListing]
    total: int
    page: int
    pageSize: int
