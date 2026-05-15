// @vitest-environment node

import { readFileSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

describe('data warehouse naming', () => {
  it('uses domestic and overseas naming in user-visible data views', () => {
    const appPagesSource = readFileSync('src/config/appPages.ts', 'utf-8')
    const warehousesSource = readFileSync('src/views/data/DataWarehousesView.vue', 'utf-8')
    const inventorySource = readFileSync('src/views/data/DataInventoryView.vue', 'utf-8')
    const overseasWarehousesSource = readFileSync(
      'src/views/data/DataThirdPartyWarehousesView.vue',
      'utf-8',
    )
    const overseasInventorySource = readFileSync(
      'src/views/data/DataThirdPartyInventoryView.vue',
      'utf-8',
    )

    expect(appPagesSource).toContain("title: '国内仓'")
    expect(appPagesSource).toContain("title: '国内库存'")
    expect(appPagesSource).toContain("title: '海外仓'")
    expect(appPagesSource).toContain("title: '海外库存'")

    expect(warehousesSource).toContain('title="国内仓"')
    expect(warehousesSource).not.toContain('placeholder="类型"')
    expect(inventorySource).toContain('title="国内库存"')
    expect(inventorySource).toContain('empty-text="暂无国内库存"')

    expect(overseasWarehousesSource).toContain('title="海外仓"')
    expect(overseasWarehousesSource).not.toContain('title="三方仓"')
    expect(overseasInventorySource).toContain('title="海外库存导入"')
    expect(overseasInventorySource).toContain('title="当前海外库存"')
    expect(overseasInventorySource).toContain('确认导入会删除并重建当前海外库存，不会修改导入历史。')
  })
})
