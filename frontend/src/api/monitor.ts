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
  retry_status: string | null
  auto_retry_attempts: number
  next_retry_at: string | null
  resolved_at: string | null
  last_retry_error: string | null
  retry_source_log_id: number | null
  has_request_payload: boolean
  can_retry: boolean
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
