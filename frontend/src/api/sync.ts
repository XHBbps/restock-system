import client from './client'

export interface SchedulerJob {
  job_name: string
  next_run_time: string | null
}

export interface SchedulerStatus {
  enabled: boolean
  running: boolean
  timezone: string
  sync_interval_minutes: number
  calc_cron: string
  jobs: SchedulerJob[]
}

export async function getSchedulerStatus(): Promise<SchedulerStatus> {
  const { data } = await client.get<SchedulerStatus>('/api/sync/scheduler')
  return data
}

export async function setSchedulerStatus(enabled: boolean): Promise<SchedulerStatus> {
  const { data } = await client.post<SchedulerStatus>('/api/sync/scheduler', { enabled })
  return data
}

export interface OrderDetailRefetchPayload {
  days: number
  limit?: number
  shop_id?: string
}

export interface OrderDetailRefetchResult {
  task_id: number | null
  existing: boolean
  matched_count: number
  queued_count: number
  truncated: boolean
}

export async function refetchOrderDetail(
  payload: OrderDetailRefetchPayload
): Promise<OrderDetailRefetchResult> {
  const { data } = await client.post<OrderDetailRefetchResult>('/api/sync/order-detail/refetch', payload)
  return data
}
