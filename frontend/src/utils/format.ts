import dayjs from 'dayjs'

/** MM-DD HH:mm — 用于数据表格中的简短时间展示 */
export function formatShortTime(value?: string | null): string {
  if (!value) return '-'
  return dayjs(value).format('MM-DD HH:mm')
}

/** YYYY-MM-DD HH:mm — 用于需要完整日期的场景（订单、历史记录） */
export function formatDateTime(value?: string | null): string {
  if (!value) return '-'
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

/** MM-DD HH:mm:ss — 用于监控/同步日志的精确时间 */
export function formatDetailTime(value?: string | null): string {
  return value ? dayjs(value).format('MM-DD HH:mm:ss') : '暂无记录'
}

/** 限制页码不越界 */
export function clampPage(currentPage: number, total: number, pageSize: number): number {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  return Math.min(Math.max(currentPage, 1), totalPages)
}
