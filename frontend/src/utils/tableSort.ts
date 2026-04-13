export type SortOrder = 'asc' | 'desc'
export type TableSortOrder = 'ascending' | 'descending'

export interface SortState {
  prop?: string
  order?: SortOrder
}

export interface SortChangeEvent {
  prop: string | null
  order: TableSortOrder | null
}

export type RowComparator<T> = (left: T, right: T) => number

export function normalizeSortOrder(order: TableSortOrder | null | undefined): SortOrder | undefined {
  if (order === 'ascending') return 'asc'
  if (order === 'descending') return 'desc'
  return undefined
}

export function compareNullable<T>(
  left: T | null | undefined,
  right: T | null | undefined,
  compare: (leftValue: T, rightValue: T) => number,
): number {
  const leftMissing = left === null || left === undefined
  const rightMissing = right === null || right === undefined
  if (leftMissing && rightMissing) return 0
  if (leftMissing) return 1
  if (rightMissing) return -1
  return compare(left, right)
}

export function compareText(left: string | null | undefined, right: string | null | undefined): number {
  return compareNullable(left, right, (leftValue, rightValue) => leftValue.localeCompare(rightValue, 'zh-CN'))
}

export function compareNumber(left: number | null | undefined, right: number | null | undefined): number {
  return compareNullable(left, right, (leftValue, rightValue) => leftValue - rightValue)
}

export function compareDateText(left: string | null | undefined, right: string | null | undefined): number {
  return compareNullable(left, right, (leftValue, rightValue) => {
    const leftTime = Date.parse(leftValue)
    const rightTime = Date.parse(rightValue)
    if (Number.isNaN(leftTime) && Number.isNaN(rightTime)) return 0
    if (Number.isNaN(leftTime)) return 1
    if (Number.isNaN(rightTime)) return -1
    return leftTime - rightTime
  })
}

export function applyLocalSort<T>(
  rows: T[],
  sortState: SortState,
  comparators: Record<string, RowComparator<T>>,
  fallbackComparator?: RowComparator<T>,
): T[] {
  const baseRows = [...rows]
  const comparator = sortState.prop ? comparators[sortState.prop] : fallbackComparator
  if (!comparator) return baseRows

  const direction = sortState.order === 'desc' ? -1 : 1
  return baseRows.sort((left, right) => comparator(left, right) * direction)
}
