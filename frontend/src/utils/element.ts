import type { TagProps } from 'element-plus'

export type TagType = NonNullable<TagProps['type']>

export function normalizeSwitchValue(value: string | number | boolean): boolean {
  if (typeof value === 'boolean') {
    return value
  }
  if (typeof value === 'number') {
    return value !== 0
  }

  const normalized = value.trim().toLowerCase()
  if (normalized === 'false' || normalized === '0' || normalized === '') {
    return false
  }
  return true
}
