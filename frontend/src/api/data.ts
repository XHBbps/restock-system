// 外部数据源 API 客户端（字段和赛狐接口一致，camelCase）
import type { SortOrder } from '@/utils/tableSort'
import client from './client'

// ========== 订单 ==========
export interface DataOrderSummary {
  shopId: string
  amazonOrderId: string
  orderPlatform: string
  packageSn: string
  packageStatus: string | null
  shopName: string | null
  postalCode: string | null
  marketplaceId: string
  countryCode: string
  orderStatus: string
  orderTotalCurrency: string | null
  orderTotalAmount: string | null
  fulfillmentChannel: string | null
  purchaseDate: string
  purchaseDateLocal?: string | null
  lastUpdateDate: string
  lastUpdateDateLocal?: string | null
  displayTimezone?: string | null
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
  stateOrRegion: string | null
  city: string | null
  detailAddress: string | null
  receiverName: string | null
  detailFetchedAt: string | null
}

export interface DataOrderPatch {
  countryCode?: string | null
  postalCode?: string | null
}

export interface OrderInfoMatchError {
  row: number
  field: string
  message: string
}

export interface OrderInfoMatchPreview {
  matchedOrderCount: number
  matchedOrderIds: string[]
  updateFields: string[]
  errors: OrderInfoMatchError[]
}

export interface OrderInfoMatchApply extends OrderInfoMatchPreview {
  updatedOrderCount: number
}

export interface OrderInfoMatchApplyTask {
  taskId: number
  existing: boolean
}

export interface OrderInfoMatchActiveTask {
  taskId: number | null
}

const ORDER_INFO_MATCH_APPLY_TIMEOUT_MS = 300000

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
  shop_id?: string
  platform?: string
  status?: string
  sku?: string
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: SortOrder
}): Promise<PageResult<DataOrderSummary>> {
  const { data } = await client.get('/api/data/orders', { params })
  return data
}

export async function listOrderPlatforms(): Promise<string[]> {
  const { data } = await client.get<string[]>('/api/data/order-platforms')
  return data
}

export async function getOrderDetail(
  shopId: string,
  amazonOrderId: string,
  packageSn = ''
): Promise<DataOrderDetail> {
  const { data } = await client.get<DataOrderDetail>(
    `/api/data/orders/${encodeURIComponent(shopId)}/${encodeURIComponent(amazonOrderId)}`,
    { params: { package_sn: packageSn } }
  )
  return data
}

export async function updateOrderDetail(
  shopId: string,
  amazonOrderId: string,
  packageSn: string,
  patch: DataOrderPatch
): Promise<DataOrderDetail> {
  const { data } = await client.patch<DataOrderDetail>(
    `/api/data/orders/${encodeURIComponent(shopId)}/${encodeURIComponent(amazonOrderId)}`,
    patch,
    { params: { package_sn: packageSn } }
  )
  return data
}

export async function downloadOrderInfoMatchTemplate(fields: string[]): Promise<Blob> {
  const { data } = await client.get('/api/data/order-info-match/template', {
    params: { fields: fields.join(',') },
    responseType: 'blob',
  })
  return data
}

export async function previewOrderInfoMatch(
  file: File,
  fields: string[]
): Promise<OrderInfoMatchPreview> {
  const { data } = await client.post<OrderInfoMatchPreview>(
    '/api/data/order-info-match/preview',
    file,
    {
      params: { fields: fields.join(',') },
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
    }
  )
  return data
}

export async function downloadOrderInfoMatchErrorReport(
  file: File,
  fields: string[]
): Promise<Blob> {
  const { data } = await client.post('/api/data/order-info-match/error-report', file, {
    params: { fields: fields.join(',') },
    headers: { 'Content-Type': file.type || 'application/octet-stream' },
    responseType: 'blob',
  })
  return data
}

export async function applyOrderInfoMatch(
  file: File,
  fields: string[]
): Promise<OrderInfoMatchApply> {
  const { data } = await client.post<OrderInfoMatchApply>(
    '/api/data/order-info-match/apply',
    file,
    {
      params: { fields: fields.join(',') },
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
      timeout: ORDER_INFO_MATCH_APPLY_TIMEOUT_MS,
    }
  )
  return data
}

export async function createOrderInfoMatchApplyTask(
  file: File,
  fields: string[]
): Promise<OrderInfoMatchApplyTask> {
  const { data } = await client.post<OrderInfoMatchApplyTask>(
    '/api/data/order-info-match/apply-task',
    file,
    {
      params: { fields: fields.join(',') },
      headers: {
        'Content-Type': file.type || 'application/octet-stream',
        'X-Filename': encodeURIComponent(file.name)
      },
    }
  )
  return data
}

export async function getActiveOrderInfoMatchApplyTask(): Promise<OrderInfoMatchActiveTask> {
  const { data } = await client.get<OrderInfoMatchActiveTask>(
    '/api/data/order-info-match/apply-task/active'
  )
  return data
}

// ========== 库存明细 ==========
export interface DataInventoryItem {
  commoditySku: string
  commodityName: string | null
  mainImage: string | null
  isPackage: boolean
  warehouseId: string
  warehouseName: string
  warehouseType: number
  country: string | null
  stockAvailable: number
  stockOccupy: number
  updatedAt: string
}

export interface DataInventoryWarehouseGroup {
  warehouseId: string
  warehouseName: string
  warehouseType: number
  skuCount: number
  totalAvailable: number
  totalOccupy: number
  items: DataInventoryItem[]
}

export async function listInventory(params: {
  country?: string
  warehouse_id?: string
  sku?: string
  only_nonzero?: boolean
  is_package?: boolean
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: SortOrder
}): Promise<PageResult<DataInventoryItem>> {
  const { data } = await client.get('/api/data/inventory', { params })
  return data
}

export async function listInventoryWarehouseGroups(params: {
  country?: string
  sku?: string
  only_nonzero?: boolean
  is_package?: boolean
  page?: number
  page_size?: number
}): Promise<PageResult<DataInventoryWarehouseGroup>> {
  const { data } = await client.get('/api/data/inventory/warehouse-groups', { params })
  return data
}

// ========== 三方仓库存 ==========
export interface ThirdPartyInventoryItem {
  id: number
  warehouseId: number
  warehouseName: string
  country: string | null
  participates: boolean
  commoditySku: string
  available: number
  reserved: number
  sourceBatchId: number | null
  lastOperation: string
  updatedAt: string
}

export interface ThirdPartyInventoryWarehouseGroup {
  warehouseId: number
  warehouseName: string
  country: string | null
  participates: boolean
  skuCount: number
  totalAvailable: number
  totalReserved: number
  items: ThirdPartyInventoryItem[]
}

export interface ThirdPartyInventoryItemInput {
  warehouseId: number
  commoditySku: string
  available: number
  reserved: number
}

export interface ThirdPartyInventoryImportIssue {
  row: number
  warehouseName: string | null
  commoditySku: string | null
  message: string
}

export interface ThirdPartyInventoryImportBatch {
  id: number
  filename: string
  status: string
  rowCount: number
  validRowCount: number
  skippedRowCount: number
  newWarehouseCount: number
  unmaintainedWarehouseCount: number
  createdBy: string | null
  confirmedBy: string | null
  createdAt: string
  confirmedAt: string | null
  summary: Record<string, unknown>
}

export interface ThirdPartyInventoryPreview extends ThirdPartyInventoryImportBatch {
  newWarehouses: string[]
  unmaintainedWarehouses: string[]
  issues: ThirdPartyInventoryImportIssue[]
}

export interface ThirdPartyInventoryImportItem {
  id: number
  warehouseNameRaw: string
  warehouseId: number | null
  commoditySku: string | null
  available: number | null
  reserved: number | null
  sourceRowNo: number
  errorMessage: string | null
}

export interface ThirdPartyInventoryBatchDetail extends ThirdPartyInventoryImportBatch {
  items: ThirdPartyInventoryImportItem[]
  itemTotal: number
}

export async function listThirdPartyInventoryWarehouseGroups(params: {
  warehouse_keyword?: string
  sku?: string
  country?: string
  only_missing_country?: boolean
  only_participating?: boolean
  only_nonzero?: boolean
  page?: number
  page_size?: number
}): Promise<PageResult<ThirdPartyInventoryWarehouseGroup>> {
  const { data } = await client.get('/api/data/third-party-inventory/warehouse-groups', { params })
  return data
}

export async function previewThirdPartyInventoryImport(file: File): Promise<ThirdPartyInventoryPreview> {
  const { data } = await client.post<ThirdPartyInventoryPreview>(
    '/api/data/third-party-inventory/import/preview',
    file,
    {
      headers: {
        'Content-Type': file.type || 'application/octet-stream',
        'X-Filename': encodeURIComponent(file.name),
      },
    },
  )
  return data
}

export async function confirmThirdPartyInventoryImport(batchId: number): Promise<ThirdPartyInventoryImportBatch> {
  const { data } = await client.post<ThirdPartyInventoryImportBatch>(
    `/api/data/third-party-inventory/import/${batchId}/confirm`,
  )
  return data
}

export async function cancelThirdPartyInventoryImport(batchId: number): Promise<ThirdPartyInventoryImportBatch> {
  const { data } = await client.post<ThirdPartyInventoryImportBatch>(
    `/api/data/third-party-inventory/import/${batchId}/cancel`,
  )
  return data
}

export async function listThirdPartyInventoryBatches(params: {
  page?: number
  page_size?: number
}): Promise<PageResult<ThirdPartyInventoryImportBatch>> {
  const { data } = await client.get('/api/data/third-party-inventory/batches', { params })
  return data
}

export async function getThirdPartyInventoryBatch(
  batchId: number,
  params: { only_errors?: boolean; page?: number; page_size?: number },
): Promise<ThirdPartyInventoryBatchDetail> {
  const { data } = await client.get(`/api/data/third-party-inventory/batches/${batchId}`, { params })
  return data
}

export async function createThirdPartyInventoryItem(
  payload: ThirdPartyInventoryItemInput,
): Promise<ThirdPartyInventoryItem> {
  const { data } = await client.post('/api/data/third-party-inventory/items', payload)
  return data
}

export async function updateThirdPartyInventoryItem(
  id: number,
  payload: Partial<ThirdPartyInventoryItemInput>,
): Promise<ThirdPartyInventoryItem> {
  const { data } = await client.patch(`/api/data/third-party-inventory/items/${id}`, payload)
  return data
}

export async function deleteThirdPartyInventoryItem(id: number): Promise<void> {
  await client.delete(`/api/data/third-party-inventory/items/${id}`)
}

// ========== 其他出库 ==========
export interface DataOutRecordItem {
  commodityId: string | null
  commoditySku: string
  goods: number
  perPurchase: string | null
}

export interface DataOutRecord {
  saihuOutRecordId: string
  warehouseId: string | null
  outWarehouseNo: string | null
  targetWarehouseId: string | null
  targetWarehouseName: string | null
  targetCountry: string | null
  updateTime: string | null
  type: number | null
  typeName: string | null
  remark: string | null
  status: string | null
  isInTransit: boolean
  lastSeenAt: string
  items: DataOutRecordItem[]
}

export async function listOutRecords(params: {
  is_in_transit?: boolean
  country?: string
  type_name?: string
  sku?: string
  out_warehouse_no?: string
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: SortOrder
}): Promise<PageResult<DataOutRecord>> {
  const { data } = await client.get('/api/data/out-records', { params })
  return data
}

export async function listOutRecordTypes(): Promise<string[]> {
  const { data } = await client.get<string[]>('/api/data/out-record-types')
  return data
}

// ========== 仓库 ==========
export interface DataWarehouse {
  id: string
  name: string
  type: number
  country: string | null
  replenishSite: string | null
  totalStock: number
  lastSyncAt: string
}

export async function listDataWarehouses(): Promise<{ items: DataWarehouse[]; total: number }> {
  const { data } = await client.get('/api/data/warehouses')
  return data
}

// ========== 三方仓 ==========
export interface ThirdPartyWarehouse {
  id: number
  name: string
  country: string | null
  currentSkuCount: number
  currentTotalAvailable: number
  currentTotalReserved: number
  importItemCount: number
  createdAt: string
  updatedAt: string
}

export interface ThirdPartyWarehouseInput {
  name: string
  country?: string | null
}

export async function listThirdPartyWarehouses(params?: {
  keyword?: string
  country?: string
  only_missing_country?: boolean
  page?: number
  page_size?: number
}): Promise<PageResult<ThirdPartyWarehouse>> {
  const { data } = await client.get('/api/data/third-party-warehouses', { params })
  return data
}

export async function createThirdPartyWarehouse(
  payload: ThirdPartyWarehouseInput,
): Promise<ThirdPartyWarehouse> {
  const { data } = await client.post('/api/data/third-party-warehouses', payload)
  return data
}

export async function updateThirdPartyWarehouse(
  id: number,
  payload: Partial<ThirdPartyWarehouseInput>,
): Promise<ThirdPartyWarehouse> {
  const { data } = await client.patch(`/api/data/third-party-warehouses/${id}`, payload)
  return data
}

export async function deleteThirdPartyWarehouse(id: number): Promise<void> {
  await client.delete(`/api/data/third-party-warehouses/${id}`)
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
  commoditySku: string | null
  commodityId: string | null
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
  commodity_id: string | null
  commodity_name: string | null
  main_image: string | null
  state: string | null
  is_group: boolean | null
  purchase_days: number | null
  has_listing: boolean
  enabled: boolean
  lead_time_days: number | null
  listing_count: number
  total_day30_sales: number
  listings: SkuListingItem[]
}

export async function listSkuOverview(params: {
  keyword?: string
  enabled?: boolean
  is_group?: boolean
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
