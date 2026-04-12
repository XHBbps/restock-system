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
