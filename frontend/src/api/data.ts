// 外部数据源 API 客户端（字段和赛狐接口一致，camelCase）
import client from './client'

// ========== 订单 ==========
export interface DataOrderSummary {
  shopId: string
  amazonOrderId: string
  marketplaceId: string
  countryCode: string
  orderStatus: string
  orderTotalCurrency: string | null
  orderTotalAmount: string | null
  fulfillmentChannel: string | null
  purchaseDate: string
  lastUpdateDate: string
  refundStatus: string | null
  lastSyncAt: string
  hasDetail: boolean
  itemCount: number
}

export interface DataOrderItem {
  orderItemId: string
  commoditySku: string
  sellerSku: string | null
  quantityOrdered: number
  quantityShipped: number
  quantityUnfulfillable: number
  refundNum: number
  itemPriceCurrency: string | null
  itemPriceAmount: string | null
}

export interface DataOrderDetail extends Omit<DataOrderSummary, 'hasDetail' | 'itemCount'> {
  isBuyerRequestedCancel: boolean
  items: DataOrderItem[]
  postalCode: string | null
  stateOrRegion: string | null
  city: string | null
  detailAddress: string | null
  receiverName: string | null
  detailFetchedAt: string | null
}

export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

export async function listOrders(params: {
  date_from?: string
  date_to?: string
  country?: string
  status?: string
  sku?: string
  page?: number
  page_size?: number
}): Promise<PageResult<DataOrderSummary>> {
  const { data } = await client.get('/api/data/orders', { params })
  return data
}

export async function getOrderDetail(
  shopId: string,
  amazonOrderId: string
): Promise<DataOrderDetail> {
  const { data } = await client.get<DataOrderDetail>(
    `/api/data/orders/${encodeURIComponent(shopId)}/${encodeURIComponent(amazonOrderId)}`
  )
  return data
}

// ========== 库存明细 ==========
export interface DataInventoryItem {
  commoditySku: string
  commodityName: string | null
  mainImage: string | null
  warehouseId: string
  warehouseName: string
  warehouseType: number
  country: string | null
  stockAvailable: number
  stockOccupy: number
  updatedAt: string
}

export async function listInventory(params: {
  country?: string
  warehouse_id?: string
  sku?: string
  only_nonzero?: boolean
  page?: number
  page_size?: number
}): Promise<PageResult<DataInventoryItem>> {
  const { data } = await client.get('/api/data/inventory', { params })
  return data
}

// ========== 其他出库 ==========
export interface DataOutRecordItem {
  commoditySku: string
  goods: number
}

export interface DataOutRecord {
  saihuOutRecordId: string
  outWarehouseNo: string | null
  targetWarehouseId: string | null
  targetWarehouseName: string | null
  targetCountry: string | null
  remark: string | null
  status: string | null
  isInTransit: boolean
  lastSeenAt: string
  items: DataOutRecordItem[]
}

export async function listOutRecords(params: {
  is_in_transit?: boolean
  country?: string
  sku?: string
  page?: number
  page_size?: number
}): Promise<PageResult<DataOutRecord>> {
  const { data } = await client.get('/api/data/out-records', { params })
  return data
}

// ========== 仓库 ==========
export interface DataWarehouse {
  id: string
  name: string
  type: number
  country: string | null
  replenishSite: string | null
  lastSyncAt: string
}

export async function listDataWarehouses(): Promise<{ items: DataWarehouse[]; total: number }> {
  const { data } = await client.get('/api/data/warehouses')
  return data
}

// ========== 店铺 ==========
export interface DataShop {
  id: string
  name: string
  sellerId: string | null
  region: string | null
  marketplaceId: string | null
  status: string
  adStatus: string | null
  syncEnabled: boolean
  lastSyncAt: string | null
}

export async function listDataShops(): Promise<{ items: DataShop[]; total: number }> {
  const { data } = await client.get('/api/data/shops')
  return data
}

// ========== 在线产品信息 ==========
export interface DataProductListing {
  id: number
  commoditySku: string
  commodityId: string
  commodityName: string | null
  mainImage: string | null
  shopId: string
  marketplaceId: string
  sellerSku: string | null
  parentSku: string | null
  day7SaleNum: number | null
  day14SaleNum: number | null
  day30SaleNum: number | null
  isMatched: boolean
  onlineStatus: string
  lastSyncAt: string
}

export async function listDataProductListings(params: {
  shop_id?: string
  marketplace_id?: string
  sku?: string
  only_matched?: boolean
  only_active?: boolean
  page?: number
  page_size?: number
}): Promise<PageResult<DataProductListing>> {
  const { data } = await client.get('/api/data/product-listings', { params })
  return data
}

// ========== SKU Overview (grouped) ==========
export interface SkuListingItem {
  id: number
  shop_id: string
  marketplace_id: string
  seller_sku: string | null
  day7_sale_num: number | null
  day14_sale_num: number | null
  day30_sale_num: number | null
  online_status: string
  last_sync_at: string | null
}

export interface SkuOverviewItem {
  commodity_sku: string
  commodity_name: string | null
  main_image: string | null
  enabled: boolean
  lead_time_days: number | null
  listing_count: number
  total_day30_sales: number
  listings: SkuListingItem[]
}

export async function listSkuOverview(params: {
  keyword?: string
  enabled?: boolean
  page?: number
  page_size?: number
}): Promise<PageResult<SkuOverviewItem>> {
  const { data } = await client.get('/api/data/sku-overview', { params })
  return data
}

// ========== Sync state ==========
export interface SyncStateRow {
  job_name: string
  last_run_at: string | null
  last_success_at: string | null
  last_status: string | null
  last_error: string | null
}

export async function listSyncState(): Promise<SyncStateRow[]> {
  const { data } = await client.get<SyncStateRow[]>('/api/data/sync-state')
  return data
}
