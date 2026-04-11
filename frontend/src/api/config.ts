// 配置 API 客户端
import client from './client'

// ========== Global Config ==========
export interface GlobalConfig {
  buffer_days: number
  target_days: number
  lead_time_days: number
  sync_interval_minutes: number
  calc_cron: string
  calc_enabled: boolean
  default_purchase_warehouse_id: string | null
  include_tax: '0' | '1'
  shop_sync_mode: 'all' | 'specific'
}

export async function getGlobalConfig(): Promise<GlobalConfig> {
  const { data } = await client.get<GlobalConfig>('/api/config/global')
  return data
}

export async function patchGlobalConfig(patch: Partial<GlobalConfig>): Promise<GlobalConfig> {
  const { data } = await client.patch<GlobalConfig>('/api/config/global', patch)
  return data
}

// ========== SKU Config ==========
export interface SkuConfig {
  commodity_sku: string
  enabled: boolean
  lead_time_days: number | null
  commodity_name: string | null
  main_image: string | null
}

export async function listSkuConfigs(params: {
  enabled?: boolean
  keyword?: string
  page?: number
  page_size?: number
}): Promise<{ items: SkuConfig[]; total: number }> {
  const { data } = await client.get('/api/config/sku', { params })
  return data
}

export async function patchSkuConfig(
  commoditySku: string,
  patch: { enabled?: boolean; lead_time_days?: number | null }
): Promise<SkuConfig> {
  const { data } = await client.patch<SkuConfig>(`/api/config/sku/${commoditySku}`, patch)
  return data
}

export async function initSkuConfigs(): Promise<{ created: number; total: number }> {
  const { data } = await client.post('/api/config/sku/init')
  return data
}

// ========== Warehouse ==========
export interface Warehouse {
  id: string
  name: string
  type: number
  country: string | null
  replenish_site_raw: string | null
  total_stock: number
}

export async function listWarehouses(): Promise<Warehouse[]> {
  const { data } = await client.get<Warehouse[]>('/api/config/warehouse')
  return data
}

export async function refreshWarehouses(): Promise<{ task_id: number; existing: boolean }> {
  const { data } = await client.post('/api/sync/warehouse')
  return data
}

export async function patchWarehouseCountry(
  warehouseId: string,
  country: string | null
): Promise<Warehouse> {
  const { data } = await client.patch<Warehouse>(
    `/api/config/warehouse/${warehouseId}/country`,
    { country }
  )
  return data
}

// ========== Zipcode Rule ==========
export interface ZipcodeRule {
  id: number
  country: string
  prefix_length: number
  value_type: 'number' | 'string'
  operator: '=' | '!=' | '>' | '>=' | '<' | '<=' | 'contains' | 'not_contains'
  compare_value: string
  warehouse_id: string
  priority: number
}

export type ZipcodeRuleInput = Omit<ZipcodeRule, 'id'>

export async function listZipcodeRules(country?: string): Promise<ZipcodeRule[]> {
  const { data } = await client.get<ZipcodeRule[]>('/api/config/zipcode-rules', {
    params: country ? { country } : {}
  })
  return data
}

export async function createZipcodeRule(rule: ZipcodeRuleInput): Promise<ZipcodeRule> {
  const { data } = await client.post<ZipcodeRule>('/api/config/zipcode-rules', rule)
  return data
}

export async function updateZipcodeRule(id: number, rule: ZipcodeRuleInput): Promise<ZipcodeRule> {
  const { data } = await client.patch<ZipcodeRule>(`/api/config/zipcode-rules/${id}`, rule)
  return data
}

export async function deleteZipcodeRule(id: number): Promise<void> {
  await client.delete(`/api/config/zipcode-rules/${id}`)
}

// ========== Shop ==========
export interface Shop {
  id: string
  name: string
  seller_id: string | null
  region: string | null
  marketplace_id: string | null
  status: string
  sync_enabled: boolean
}

export async function listShops(): Promise<Shop[]> {
  const { data } = await client.get<Shop[]>('/api/config/shops')
  return data
}

export async function refreshShops(): Promise<{ task_id: number; existing: boolean }> {
  const { data } = await client.post('/api/config/shops/refresh')
  return data
}

export async function patchShop(shopId: string, syncEnabled: boolean): Promise<Shop> {
  const { data } = await client.patch<Shop>(`/api/config/shops/${shopId}`, {
    sync_enabled: syncEnabled
  })
  return data
}
