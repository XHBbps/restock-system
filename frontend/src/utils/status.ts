import type { TagType } from './element'

interface StatusMeta {
  label: string
  tagType: TagType
}

const fallbackMeta = (value: string, tagType: TagType = 'info'): StatusMeta => ({
  label: value || '未知',
  tagType,
})

const suggestionStatusMap: Record<string, StatusMeta> = {
  draft: { label: '草稿', tagType: 'warning' },
  archived: { label: '已归档', tagType: 'info' },
  error: { label: '异常', tagType: 'danger' },
}

// 派生的 4 档显示状态：未提交 / 已导出 / 已归档 / 异常
// - draft + snapshot_count=0 → 未提交
// - draft + snapshot_count>0 → 已导出（包含分批导出的中间态）
// - archived → 已归档
// - error → 异常（兜底）
const suggestionDisplayStatusMap: Record<string, StatusMeta> = {
  pending: { label: '未提交', tagType: 'warning' },
  exported: { label: '已导出', tagType: 'success' },
  archived: { label: '已归档', tagType: 'info' },
  error: { label: '异常', tagType: 'danger' },
}

export type SuggestionDisplayStatus = 'pending' | 'exported' | 'archived' | 'error'

export function deriveSuggestionDisplayStatus(
  status: string,
  snapshotCount: number,
): SuggestionDisplayStatus {
  if (status === 'archived') return 'archived'
  if (status === 'error') return 'error'
  return snapshotCount > 0 ? 'exported' : 'pending'
}

const syncStatusMap: Record<string, StatusMeta> = {
  success: { label: '成功', tagType: 'success' },
  failed: { label: '失败', tagType: 'danger' },
  running: { label: '执行中', tagType: 'warning' },
  pending: { label: '排队中', tagType: 'warning' },
  queued: { label: '排队中', tagType: 'warning' },
  completed: { label: '已完成', tagType: 'success' },
  idle: { label: '未执行', tagType: 'info' },
}

const shopStatusMap: Record<string, StatusMeta> = {
  '0': { label: '正常', tagType: 'success' },
  '1': { label: '授权失效', tagType: 'danger' },
  '2': { label: 'SP 授权失效', tagType: 'warning' },
}

export function getSuggestionStatusMeta(status: string): StatusMeta {
  return suggestionStatusMap[status] || fallbackMeta(status)
}

export function getSuggestionDisplayStatusMeta(
  status: string,
  snapshotCount: number,
): StatusMeta {
  const derived = deriveSuggestionDisplayStatus(status, snapshotCount)
  return suggestionDisplayStatusMap[derived] || fallbackMeta(status)
}

export function getSyncStatusMeta(status: string | null | undefined): StatusMeta {
  if (!status) return { label: '未执行', tagType: 'info' }
  return syncStatusMap[status] || fallbackMeta(status)
}

export function getShopStatusMeta(status: string): StatusMeta {
  return shopStatusMap[status] || fallbackMeta('未知状态')
}

export function getListingOnlineStatusMeta(status: string | null | undefined): StatusMeta {
  const normalized = String(status || '').trim().toLowerCase()
  if (!normalized) return fallbackMeta('未知')
  if (normalized === 'active') {
    return { label: '在售', tagType: 'success' }
  }
  return { label: '不在售', tagType: 'info' }
}

export function getOutRecordTransitStatusMeta(isInTransit: boolean): StatusMeta {
  return isInTransit
    ? { label: '在途', tagType: 'success' }
    : { label: '完结', tagType: 'info' }
}
