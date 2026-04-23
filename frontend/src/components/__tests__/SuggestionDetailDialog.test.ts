// @vitest-environment jsdom

import { shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import type { SnapshotItemOut } from '@/api/snapshot'

vi.mock('@/api/config', () => ({
  listWarehouses: vi.fn().mockResolvedValue([]),
}))

vi.mock('@/api/snapshot', () => ({
  listSnapshots: vi.fn().mockResolvedValue([]),
  getSnapshot: vi.fn(),
  downloadSnapshotBlob: vi.fn(),
}))

const STUBS = {
  ElDialog: { template: '<div><slot /><slot name="header" /></div>' },
  ElButton: true,
  ElTable: { template: '<div><slot /></div>' },
  ElTableColumn: true,
  ElTag: { template: '<span><slot /></span>' },
  SkuCard: true,
  PurchaseDateCell: true,
  X: true,
}

function makeSnapshotItem(overrides: Partial<SnapshotItemOut> = {}): SnapshotItemOut {
  return {
    id: 1,
    commodity_sku: 'SKU-001',
    commodity_name: 'Demo',
    main_image_url: null,
    total_qty: 15,
    country_breakdown: { US: 10, GB: 5 },
    warehouse_breakdown: { US: { 'WH-1': 10 }, GB: { 'WH-2': 5 } },
    restock_dates: { US: '2026-05-10', GB: '2026-05-01' },
    purchase_qty: null,
    purchase_date: null,
    urgent: false,
    velocity_snapshot: null,
    sale_days_snapshot: null,
    ...overrides,
  }
}

describe('SuggestionDetailDialog', () => {
  it('computes snapshot restock dates for summary and country rows', async () => {
    const { default: View } = await import('../SuggestionDetailDialog.vue')
    const wrapper = shallowMount(View, {
      props: {
        modelValue: true,
        suggestionId: 1,
        type: 'restock',
      },
      global: { stubs: STUBS },
    })

    const vm = wrapper.vm as unknown as {
      itemCountryRows: (item: SnapshotItemOut) => { country: string; restockDate: string | null }[]
      restockDateSummary: (item: SnapshotItemOut) => string
    }
    const item = makeSnapshotItem()

    expect(vm.itemCountryRows(item).map((row) => [row.country, row.restockDate])).toEqual([
      ['US', '2026-05-10'],
      ['GB', '2026-05-01'],
    ])
    expect(vm.restockDateSummary(item)).toBe('2026-05-01')
  })
})
