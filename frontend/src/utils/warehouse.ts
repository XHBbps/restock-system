/** 仓库类型映射和标签 — 统一 DataWarehousesView 和 DataInventoryView 的展示 */

export const WAREHOUSE_TYPE_MAP: Record<number, string> = {
  [-1]: '虚拟仓',
  0: '默认仓',
  1: '国内仓',
  2: 'FBA 仓',
  3: '海外仓',
}

export function warehouseTypeLabel(type: number): string {
  return WAREHOUSE_TYPE_MAP[type] ?? `未知(${type})`
}

export function warehouseTypeTag(type: number): 'primary' | 'success' | 'warning' | 'info' {
  switch (type) {
    case 1:
      return 'success'
    case 2:
      return 'primary'
    case 3:
      return 'warning'
    default:
      return 'info'
  }
}
