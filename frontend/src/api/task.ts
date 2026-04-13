// Task API 客户端（用于轮询任务进度）
import client from './client'

export type TaskStatus =
  | 'pending'
  | 'running'
  | 'success'
  | 'failed'
  | 'skipped'
  | 'cancelled'

export interface TaskRun {
  id: number
  job_name: string
  dedupe_key: string
  status: TaskStatus
  trigger_source: 'scheduler' | 'manual'
  priority: number
  payload: Record<string, unknown>
  current_step: string | null
  step_detail: string | null
  total_steps: number | null
  attempt_count: number
  error_msg: string | null
  result_summary: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export async function getTask(taskId: number): Promise<TaskRun> {
  const { data } = await client.get<TaskRun>(`/api/tasks/${taskId}`)
  return data
}
