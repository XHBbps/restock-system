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
  suggestion_item_count: number
  pushed_count: number
  urgent_count: number
  warning_count: number
  safe_count: number
  risk_country_count: number
  suggestion_id: number | null
  suggestion_status: string | null
  lead_time_days: number
  target_days: number
  country_risk_distribution: CountryRiskDistribution[]
  country_restock_distribution: CountryRestockDistribution[]
  top_urgent_skus: UrgentSkuItem[]
}

export async function getDashboardOverview(): Promise<DashboardOverview> {
  const { data } = await client.get<DashboardOverview>('/api/metrics/dashboard')
  return data
}
