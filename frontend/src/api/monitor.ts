// 监控 API 客户端
import client from './client'

export interface EndpointStats {
  endpoint: string
  total_calls: number
  success_count: number
  failed_count: number
  success_rate: number
  last_called_at: string | null
  last_status: string | null
  last_error: string | null
}

export interface ApiCallsOverview {
  endpoints: EndpointStats[]
  postal_compliance_warning: number
}

export interface RecentCall {
  id: number
  endpoint: string
  called_at: string
  duration_ms: number | null
  http_status: number | null
  saihu_code: number | null
  saihu_msg: string | null
  error_type: string | null
}

export async function getApiCallsOverview(hours = 24): Promise<ApiCallsOverview> {
  const { data } = await client.get<ApiCallsOverview>('/api/monitor/api-calls', {
    params: { hours }
  })
  return data
}

export async function getRecentCalls(params: {
  endpoint?: string
  only_failed?: boolean
  limit?: number
}): Promise<RecentCall[]> {
  const { data } = await client.get<RecentCall[]>('/api/monitor/api-calls/recent', { params })
  return data
}

export async function retryCall(id: number): Promise<{ task_id: number | null; existing?: boolean }> {
  const { data } = await client.post(`/api/monitor/api-calls/${id}/retry`)
  return data
}

// ========== Overstock ==========
export interface Overstock {
  id: number
  commodity_sku: string
  commodity_name: string | null
  country: string
  warehouse_id: string
  warehouse_name: string | null
  current_stock: number
  last_sale_date: string | null
  processed_at: string | null
  note: string | null
}

export async function listOverstock(params: {
  show_processed?: boolean
  country?: string
}): Promise<Overstock[]> {
  const { data } = await client.get<Overstock[]>('/api/monitor/overstock', { params })
  return data
}

export async function markOverstockProcessed(id: number, note?: string): Promise<void> {
  await client.patch(`/api/monitor/overstock/${id}/processed`, { note })
}
