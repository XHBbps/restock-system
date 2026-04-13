import { describe, expect, it } from 'vitest'

import { formatDateTime, formatDetailTime, formatShortTime, formatUpdateTime } from './format'

describe('time format helpers', () => {
  it('formats short table times with month-day and minute precision', () => {
    expect(formatShortTime('2026-04-14T10:11:12')).toBe('04-14 10:11')
  })

  it('formats full date times with minute precision', () => {
    expect(formatDateTime('2026-04-14T10:11:12')).toBe('2026-04-14 10:11')
  })

  it('formats unified update times with second precision', () => {
    expect(formatUpdateTime('2026-04-14T10:11:12')).toBe('2026-04-14 10:11:12')
    expect(formatUpdateTime(null)).toBe('-')
  })

  it('formats monitor detail times with month-day and second precision', () => {
    expect(formatDetailTime('2026-04-14T10:11:12')).toBe('04-14 10:11:12')
  })
})
