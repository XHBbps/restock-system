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
  partial: { label: '部分推送', tagType: 'warning' },
  pushed: { label: '已推送', tagType: 'success' },
  archived: { label: '已归档', tagType: 'info' },
  error: { label: '异常', tagType: 'danger' },
}

const suggestionPushStatusMap: Record<string, StatusMeta> = {
  pending: { label: '待推送', tagType: 'warning' },
  pushed: { label: '已推送', tagType: 'success' },
  push_failed: { label: '推送失败', tagType: 'danger' },
  blocked: { label: '不可推送', tagType: 'info' },
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

export function getSuggestionPushStatusMeta(status: string): StatusMeta {
  return suggestionPushStatusMap[status] || fallbackMeta(status)
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
