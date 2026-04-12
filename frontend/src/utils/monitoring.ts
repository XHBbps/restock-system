import type { TaskStatus } from '@/api/task'

export function getPercentileIndex(length: number, percentile: number): number {
  if (length <= 0) return 0
  return Math.max(0, Math.ceil(length * percentile) - 1)
}

export function getTaskTerminalFeedback(status: TaskStatus): {
  type: 'success' | 'warning' | 'error'
  message: string
} {
  switch (status) {
    case 'success':
      return { type: 'success', message: '重试任务已成功完成，监控数据已刷新' }
    case 'failed':
      return { type: 'error', message: '重试任务执行失败，监控数据已刷新' }
    case 'skipped':
      return { type: 'warning', message: '重试任务已跳过，监控数据已刷新' }
    case 'cancelled':
      return { type: 'warning', message: '重试任务已取消，监控数据已刷新' }
    default:
      return { type: 'warning', message: '重试任务已结束，监控数据已刷新' }
  }
}
