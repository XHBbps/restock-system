import client from './client'

export interface CountryStockDays {
  country: string
  avg_sale_days: number
  sku_count: number
}

export interface UrgentSkuItem {
  commodity_sku: string
  commodity_name: string | null
  main_image: string | null
  total_qty: number
  country_breakdown: Record<string, number>
}

export interface DashboardOverview {
  enabled_sku_count: number
  suggestion_item_count: number
  pushed_count: number
  urgent_count: number
  suggestion_id: number | null
  suggestion_status: string | null
  target_days: number
  country_stock_days: CountryStockDays[]
  top_urgent_skus: UrgentSkuItem[]
}

export async function getDashboardOverview(): Promise<DashboardOverview> {
  const { data } = await client.get<DashboardOverview>('/api/metrics/dashboard')
  return data
}
