import { describe, expect, it } from 'vitest'
import {
  applyLocalSort,
  compareNumber,
  compareText,
  normalizeSortOrder,
} from '../tableSort'

describe('normalizeSortOrder', () => {
  it('converts ascending to asc', () => {
    expect(normalizeSortOrder('ascending')).toBe('asc')
  })

  it('converts descending to desc', () => {
    expect(normalizeSortOrder('descending')).toBe('desc')
  })

  it('returns undefined for null', () => {
    expect(normalizeSortOrder(null)).toBeUndefined()
  })
})

describe('compareNumber', () => {
  it('returns negative when left < right', () => {
    expect(compareNumber(1, 2)).toBeLessThan(0)
  })

  it('returns positive when left > right', () => {
    expect(compareNumber(5, 3)).toBeGreaterThan(0)
  })

  it('returns 0 for equal values', () => {
    expect(compareNumber(4, 4)).toBe(0)
  })

  it('pushes null to end', () => {
    expect(compareNumber(null, 5)).toBe(1)
    expect(compareNumber(5, null)).toBe(-1)
  })
})

describe('compareText', () => {
  it('compares strings with zh-CN locale', () => {
    expect(compareText('a', 'b')).toBeLessThan(0)
  })

  it('pushes null to end', () => {
    expect(compareText(null, 'a')).toBe(1)
  })
})

describe('applyLocalSort', () => {
  const items = [
    { id: 1, name: 'B', qty: 10 },
    { id: 2, name: 'A', qty: 20 },
    { id: 3, name: 'C', qty: 5 },
  ]

  it('sorts ascending by comparator', () => {
    const result = applyLocalSort(items, { prop: 'qty', order: 'asc' }, {
      qty: (a, b) => compareNumber(a.qty, b.qty),
    })
    expect(result.map((r) => r.id)).toEqual([3, 1, 2])
  })

  it('sorts descending', () => {
    const result = applyLocalSort(items, { prop: 'qty', order: 'desc' }, {
      qty: (a, b) => compareNumber(a.qty, b.qty),
    })
    expect(result.map((r) => r.id)).toEqual([2, 1, 3])
  })

  it('uses fallback when no prop match', () => {
    const result = applyLocalSort(items, {}, {}, (a, b) => compareNumber(a.id, b.id))
    expect(result.map((r) => r.id)).toEqual([1, 2, 3])
  })
})
