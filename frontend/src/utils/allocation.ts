import type { AllocationExplanation } from '@/api/suggestion'
import type { TagType } from '@/utils/element'

export function allocationModeLabel(mode: AllocationExplanation['allocation_mode']): string {
  switch (mode) {
    case 'matched':
      return '规则分配'
    case 'fallback_even':
      return '均分兜底'
    case 'no_warehouse':
      return '无可用仓'
  }
}

export function allocationModeTagType(mode: AllocationExplanation['allocation_mode']): TagType {
  switch (mode) {
    case 'matched':
      return 'success'
    case 'fallback_even':
      return 'warning'
    case 'no_warehouse':
      return 'danger'
  }
}

export function allocationSummary(explanation: AllocationExplanation): string {
  return `已知样本 ${explanation.matched_order_qty} / 未知样本 ${explanation.unknown_order_qty}`
}
