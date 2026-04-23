// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import type { SuggestionDetail, SuggestionItem } from '@/api/suggestion'

const mockPatchSuggestionItem = vi.fn()
const mockCreateProcurementSnapshot = vi.fn()
const mockDownloadSnapshotBlob = vi.fn()
const mockTriggerBlobDownload = vi.fn()

vi.mock('@/api/suggestion', async () => {
  const actual = await vi.importActual<typeof import('@/api/suggestion')>('@/api/suggestion')
  return {
    ...actual,
    patchSuggestionItem: (...args: unknown[]) => mockPatchSuggestionItem(...args),
  }
})

vi.mock('@/api/snapshot', () => ({
  createProcurementSnapshot: (...args: unknown[]) => mockCreateProcurementSnapshot(...args),
  downloadSnapshotBlob: (...args: unknown[]) => mockDownloadSnapshotBlob(...args),
}))

vi.mock('@/utils/download', () => ({
  triggerBlobDownload: (...args: unknown[]) => mockTriggerBlobDownload(...args),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn() },
  }
})

function makeItem(id: number, overrides: Partial<SuggestionItem> = {}): SuggestionItem {
  return {
    id,
    commodity_sku: `SKU-${id}`,
    commodity_name: null,
    main_image: null,
    total_qty: 10,
    country_breakdown: { US: 10 },
    warehouse_breakdown: { US: { 'WH-1': 10 } },
    restock_dates: { US: '2026-04-30' },
    allocation_snapshot: null,
    velocity_snapshot: null,
    sale_days_snapshot: null,
    urgent: false,
    purchase_qty: 10,
    purchase_date: '2026-04-30',
    procurement_export_status: 'pending',
    procurement_exported_snapshot_id: null,
    procurement_exported_at: null,
    restock_export_status: 'pending',
    restock_exported_snapshot_id: null,
    restock_exported_at: null,
    ...overrides,
  }
}

function makeSuggestion(overrides: Partial<SuggestionDetail> = {}): SuggestionDetail {
  return {
    id: 1,
    status: 'draft',
    triggered_by: 'manual',
    total_items: 2,
    procurement_item_count: 1,
    restock_item_count: 1,
    procurement_snapshot_count: 0,
    restock_snapshot_count: 0,
    archived_trigger: null,
    procurement_display_status: '未导出',
    restock_display_status: '未导出',
    procurement_display_status_code: 'pending',
    restock_display_status_code: 'pending',
    global_config_snapshot: {},
    created_at: '2026-04-21T10:00:00',
    archived_at: null,
    items: [],
    ...overrides,
  }
}

const STUBS = {
  ElEmpty: true,
  ElInput: true,
  ElButton: true,
  ElTable: { template: '<div><slot /></div>' },
  ElTableColumn: true,
  ElInputNumber: true,
  ElDatePicker: true,
  ElTag: { template: '<span><slot /></span>' },
  SkuCard: true,
  PurchaseDateCell: true,
}

describe('ProcurementListView', () => {
  it('filters out rows without purchase quantity and sorts by purchase date', async () => {
    const { default: View } = await import('../ProcurementListView.vue')
    const wrapper = shallowMount(View, {
      props: {
        suggestion: makeSuggestion(),
        items: [
          makeItem(1, { purchase_qty: 0, purchase_date: '2026-04-21' }),
          makeItem(2, { purchase_qty: 5, purchase_date: '2026-04-25' }),
          makeItem(3, { purchase_qty: 6, purchase_date: '2026-04-22' }),
        ],
      },
      global: { stubs: STUBS },
    })
    await flushPromises()

    const vm = wrapper.vm as unknown as { filteredItems: SuggestionItem[] }
    expect(vm.filteredItems.map((item) => item.id)).toEqual([3, 2])
  })

  it('shows empty state when there is no procurement demand', async () => {
    const { default: View } = await import('../ProcurementListView.vue')
    const wrapper = shallowMount(View, {
      props: { suggestion: makeSuggestion({ procurement_item_count: 0 }), items: [] },
      global: { stubs: STUBS },
    })

    expect(wrapper.findComponent({ name: 'ElEmpty' }).exists()).toBe(true)
  })
})
