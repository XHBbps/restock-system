import client from './client'

export interface CountryRiskDistribution {
  country: string
  urgent_count: number
  warning_count: number
  safe_count: number
  total_count: number
}

export interface CountryRestockDistribution {
  country: string
  total_qty: number
}

export interface UrgentSkuItem {
  commodity_sku: string
  commodity_name: string | null
  main_image: string | null
  country: string
  sale_days: number | null
}

export interface DashboardOverview {
  enabled_sku_count: number
  restock_sku_count: number
  no_restock_sku_count: number
  suggestion_item_count: number
  exported_count: number
  urgent_count: number
  warning_count: number
  safe_count: number
  risk_country_count: number
  suggestion_id: number | null
  suggestion_status: string | null
  suggestion_snapshot_count: number
  lead_time_days: number
  target_days: number
  country_risk_distribution: CountryRiskDistribution[]
  country_restock_distribution: CountryRestockDistribution[]
  top_urgent_skus: UrgentSkuItem[]
  snapshot_status: 'ready' | 'missing' | 'refreshing'
  snapshot_updated_at: string | null
  snapshot_task_id: number | null
}

export interface DashboardRefreshResult {
  task_id: number
  existing: boolean
}

export async function getDashboardOverview(): Promise<DashboardOverview> {
  const { data } = await client.get<DashboardOverview>('/api/metrics/dashboard')
  return data
}

export async function refreshDashboardSnapshot(): Promise<DashboardRefreshResult> {
  const { data } = await client.post<DashboardRefreshResult>('/api/metrics/dashboard/refresh')
  return data
}
