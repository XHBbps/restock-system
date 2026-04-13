import { describe, expect, it } from 'vitest'

import {
  formatMonitorEndpoint,
  formatPerformanceResourceName,
  getPercentileIndex,
  getTaskTerminalFeedback,
  normalizeMonitorResourceName,
} from './monitoring'

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

describe('formatMonitorEndpoint', () => {
  it('maps known saihu endpoints to Chinese labels', () => {
    expect(formatMonitorEndpoint('/api/order/detailByOrderId.json')).toEqual({
      label: '订单详情同步',
      raw: '/api/order/detailByOrderId.json',
    })
  })

  it('falls back to a readable label for unknown endpoints', () => {
    expect(formatMonitorEndpoint('/api/custom/fooBar.json')).toEqual({
      label: '赛狐接口：fooBar',
      raw: '/api/custom/fooBar.json',
    })
  })
})

describe('normalizeMonitorResourceName', () => {
  it('normalizes absolute urls into path and query', () => {
    expect(normalizeMonitorResourceName('https://example.com/api/tasks/12?verbose=1')).toBe('/api/tasks/12?verbose=1')
  })
})

describe('formatPerformanceResourceName', () => {
  it('maps monitor api requests to Chinese labels', () => {
    expect(formatPerformanceResourceName('https://example.com/api/monitor/api-calls?hours=24')).toEqual({
      label: '接口监控聚合查询',
      raw: '/api/monitor/api-calls?hours=24',
    })
  })

  it('maps navigation entries to page labels', () => {
    expect(formatPerformanceResourceName('https://example.com/settings/performance', 'navigation')).toEqual({
      label: '页面导航：/settings/performance',
      raw: '/settings/performance',
    })
  })

  it('maps static assets to readable Chinese resource labels', () => {
    expect(formatPerformanceResourceName('https://example.com/assets/app-123.js')).toEqual({
      label: '构建产物资源：app-123.js',
      raw: '/assets/app-123.js',
    })
  })
})
