import { describe, expect, it } from 'vitest'

import { allocationModeLabel, allocationModeTagType, allocationSummary } from './allocation'

describe('allocation helpers', () => {
  it('maps allocation mode to labels and tag types', () => {
    expect(allocationModeLabel('matched')).toBe('规则分配')
    expect(allocationModeTagType('matched')).toBe('success')
    expect(allocationModeLabel('fallback_even')).toBe('均分兜底')
    expect(allocationModeTagType('fallback_even')).toBe('warning')
    expect(allocationModeLabel('no_warehouse')).toBe('无可用仓')
    expect(allocationModeTagType('no_warehouse')).toBe('danger')
  })

  it('formats allocation summary', () => {
    expect(
      allocationSummary({
        allocation_mode: 'fallback_even',
        matched_order_qty: 0,
        unknown_order_qty: 12,
        eligible_warehouses: ['haiyuan', 'xiapu']
      })
    ).toBe('已知样本 0 / 未知样本 12')
  })
})
