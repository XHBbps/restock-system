// @vitest-environment node

import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

describe('data view time labels', () => {
  it('uses 同步时间 for data sync columns and keeps 更新时间 in out records', () => {
    const productsSource = readFileSync('src/views/data/DataProductsView.vue', 'utf-8')
    const shopsSource = readFileSync('src/views/data/DataShopsView.vue', 'utf-8')
    const warehousesSource = readFileSync('src/views/data/DataWarehousesView.vue', 'utf-8')
    const inventorySource = readFileSync('src/views/data/DataInventoryView.vue', 'utf-8')
    const outRecordsSource = readFileSync('src/views/data/DataOutRecordsView.vue', 'utf-8')

    expect(productsSource).toContain('label="同步时间"')
    expect(productsSource).not.toContain('label="最后同步"')

    expect(shopsSource).toContain('label="同步时间"')
    expect(shopsSource).not.toContain('label="最近同步"')

    expect(warehousesSource).toContain('label="同步时间"')
    expect(warehousesSource).not.toContain('label="最近同步"')

    expect(inventorySource).toContain('label="同步时间"')
    expect(outRecordsSource).toContain('label="更新时间"')
    expect(outRecordsSource).toContain('label="同步时间"')
  })
})
