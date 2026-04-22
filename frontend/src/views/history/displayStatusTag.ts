import type { SuggestionDisplayStatusCode } from '@/api/suggestion'

export type ElTagType = 'success' | 'warning' | 'info' | 'danger'

// Tag 色按后端 code 映射，而非中文字面量；label 仍由后端返回。
// 新增 error code 专供渲染生成失败的建议单。
export const STATUS_TAG_MAP: Record<SuggestionDisplayStatusCode, ElTagType> = {
  exported: 'success',
  pending: 'warning',
  archived: 'info',
  error: 'danger',
}

export function statusTagType(code: SuggestionDisplayStatusCode): ElTagType {
  return STATUS_TAG_MAP[code] ?? 'info'
}
