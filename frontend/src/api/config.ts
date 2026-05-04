import client from './client'

// ========== Global Config ==========
export interface GlobalConfig {
  buffer_days: number
  target_days: number
  lead_time_days: number
  safety_stock_days: number
  restock_regions: string[]
  eu_countries: string[]
  sync_interval_minutes: number
  scheduler_enabled: boolean
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

export interface CountryOption {
  code: string
  label: string
  builtin: boolean
  observed: boolean
  can_be_eu_member: boolean
}

export interface CountryOptionsResponse {
  items: CountryOption[]
  unknown_country_codes: string[]
}

export async function getCountryOptions(): Promise<CountryOptionsResponse> {
  const { data } = await client.get<CountryOptionsResponse>('/api/config/country-options')
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
  patch: { enabled?: boolean; lead_time_days?: number | null },
): Promise<SkuConfig> {
  const { data } = await client.patch<SkuConfig>(`/api/config/sku/${commoditySku}`, patch)
  return data
}

export async function initSkuConfigs(): Promise<{ created: number; total: number }> {
  const { data } = await client.post('/api/config/sku/init')
  return data
}

// ========== SKU Mapping Rules ==========
export interface SkuMappingComponent {
  id: number
  group_no: number
  inventory_sku: string
  quantity: number
}

export interface SkuMappingRule {
  id: number
  commodity_sku: string
  enabled: boolean
  remark: string | null
  components: SkuMappingComponent[]
  formula_preview: string
  component_count: number
  created_at: string
  updated_at: string
}

export interface SkuMappingComponentInput {
  group_no: number
  inventory_sku: string
  quantity: number
}

export interface SkuMappingRuleInput {
  commodity_sku: string
  enabled: boolean
  remark?: string | null
  components: SkuMappingComponentInput[]
}

export async function listSkuMappingRules(params: {
  enabled?: boolean
  keyword?: string
  page?: number
  page_size?: number
}): Promise<{ items: SkuMappingRule[]; total: number }> {
  const { data } = await client.get('/api/config/sku-mapping-rules', { params })
  return data
}

export async function createSkuMappingRule(
  rule: SkuMappingRuleInput,
): Promise<SkuMappingRule> {
  const { data } = await client.post<SkuMappingRule>('/api/config/sku-mapping-rules', rule)
  return data
}

export async function updateSkuMappingRule(
  id: number,
  rule: Partial<SkuMappingRuleInput>,
): Promise<SkuMappingRule> {
  const { data } = await client.patch<SkuMappingRule>(`/api/config/sku-mapping-rules/${id}`, rule)
  return data
}

export async function deleteSkuMappingRule(id: number): Promise<void> {
  await client.delete(`/api/config/sku-mapping-rules/${id}`)
}

export async function exportSkuMappingRules(): Promise<Blob> {
  const { data } = await client.get('/api/config/sku-mapping-rules/export', {
    responseType: 'blob',
  })
  return data
}

export async function importSkuMappingRules(file: File): Promise<{
  created: number
  updated: number
  total_components: number
}> {
  const { data } = await client.post('/api/config/sku-mapping-rules/import', file, {
    headers: {
      'Content-Type': file.type || 'application/octet-stream',
      'X-Filename': encodeURIComponent(file.name),
    },
  })
  return data
}

// ========== Physical Item Groups ==========
export interface PhysicalItemAlias {
  id: number
  sku: string
}

export interface PhysicalItemGroup {
  id: number
  name: string
  primary_sku: string
  enabled: boolean
  remark: string | null
  aliases: PhysicalItemAlias[]
  alias_count: number
  created_at: string
  updated_at: string
}

export interface PhysicalItemGroupInput {
  name: string
  primary_sku: string
  enabled: boolean
  remark?: string | null
  aliases: string[]
}

export async function listPhysicalItemGroups(params: {
  enabled?: boolean
  keyword?: string
  page?: number
  page_size?: number
}): Promise<{ items: PhysicalItemGroup[]; total: number }> {
  const { data } = await client.get('/api/config/physical-item-groups', { params })
  return data
}

export async function createPhysicalItemGroup(
  group: PhysicalItemGroupInput,
): Promise<PhysicalItemGroup> {
  const { data } = await client.post<PhysicalItemGroup>('/api/config/physical-item-groups', group)
  return data
}

export async function updatePhysicalItemGroup(
  id: number,
  group: Partial<PhysicalItemGroupInput>,
): Promise<PhysicalItemGroup> {
  const { data } = await client.patch<PhysicalItemGroup>(
    `/api/config/physical-item-groups/${id}`,
    group,
  )
  return data
}

export async function deletePhysicalItemGroup(id: number): Promise<void> {
  await client.delete(`/api/config/physical-item-groups/${id}`)
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
  country: string | null,
): Promise<Warehouse> {
  const { data } = await client.patch<Warehouse>(
    `/api/config/warehouse/${warehouseId}/country`,
    { country },
  )
  return data
}

// ========== Zipcode Rule ==========
export interface ZipcodeRule {
  id: number
  country: string
  prefix_length: number
  value_type: 'number' | 'string'
  operator:
    | '='
    | '!='
    | '>'
    | '>='
    | '<'
    | '<='
    | 'contains'
    | 'not_contains'
    | 'between'
  compare_value: string
  warehouse_id: string
  priority: number
}

export type ZipcodeRuleInput = Omit<ZipcodeRule, 'id'>

export async function listZipcodeRules(country?: string): Promise<ZipcodeRule[]> {
  const { data } = await client.get<ZipcodeRule[]>('/api/config/zipcode-rules', {
    params: country ? { country } : {},
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
    sync_enabled: syncEnabled,
  })
  return data
}

// ========== Generation Toggle ==========
export interface GenerationToggle {
  enabled: boolean
  updated_by: number | null
  updated_by_name: string | null
  updated_at: string | null
  can_enable: boolean
  can_enable_reason: string | null
}

export async function getGenerationToggle(): Promise<GenerationToggle> {
  const { data } = await client.get<GenerationToggle>('/api/config/generation-toggle', {
    suppressForbiddenToast: true,
  })
  return data
}

export async function patchGenerationToggle(enabled: boolean): Promise<GenerationToggle> {
  const { data } = await client.patch<GenerationToggle>(
    '/api/config/generation-toggle',
    { enabled },
  )
  return data
}
