import { describe, expect, it } from 'vitest'

import { normalizeSwitchValue } from './element'

describe('normalizeSwitchValue', () => {
  it('preserves boolean values', () => {
    expect(normalizeSwitchValue(true)).toBe(true)
    expect(normalizeSwitchValue(false)).toBe(false)
  })

  it('normalizes numeric values', () => {
    expect(normalizeSwitchValue(1)).toBe(true)
    expect(normalizeSwitchValue(0)).toBe(false)
  })

  it('normalizes string values', () => {
    expect(normalizeSwitchValue('true')).toBe(true)
    expect(normalizeSwitchValue('1')).toBe(true)
    expect(normalizeSwitchValue('false')).toBe(false)
    expect(normalizeSwitchValue('0')).toBe(false)
    expect(normalizeSwitchValue('')).toBe(false)
  })
})
