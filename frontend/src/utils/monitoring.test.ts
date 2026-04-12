import { describe, expect, it } from 'vitest'

import { getPercentileIndex, getTaskTerminalFeedback } from './monitoring'

describe('getPercentileIndex', () => {
  it('returns 0 for empty or single-item samples', () => {
    expect(getPercentileIndex(0, 0.95)).toBe(0)
    expect(getPercentileIndex(1, 0.95)).toBe(0)
  })

  it('does not promote common sample sizes to p100', () => {
    expect(getPercentileIndex(20, 0.95)).toBe(18)
    expect(getPercentileIndex(100, 0.95)).toBe(94)
  })
})

describe('getTaskTerminalFeedback', () => {
  it('maps terminal statuses to the correct toast semantics', () => {
    expect(getTaskTerminalFeedback('success')).toEqual({
      type: 'success',
      message: '重试任务已成功完成，监控数据已刷新',
    })
    expect(getTaskTerminalFeedback('failed')).toEqual({
      type: 'error',
      message: '重试任务执行失败，监控数据已刷新',
    })
    expect(getTaskTerminalFeedback('cancelled')).toEqual({
      type: 'warning',
      message: '重试任务已取消，监控数据已刷新',
    })
  })
})
