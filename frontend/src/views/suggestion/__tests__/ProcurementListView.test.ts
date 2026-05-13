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
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
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
    calculation_inputs_snapshot: null,
    calculation_warnings: [],
    urgent: false,
    purchase_qty: 10,
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
  ElCheckbox: true,
  ElTable: { template: '<div><slot /></div>' },
  ElTableColumn: true,
  ElInputNumber: true,
  ElTag: { template: '<span><slot /></span>' },
  SkuCard: true,
}

describe('ProcurementListView', () => {
  it('selects all procurement rows across pages and exports the global selection', async () => {
    mockCreateProcurementSnapshot.mockResolvedValue({ id: 88 })
    mockDownloadSnapshotBlob.mockResolvedValue({
      blob: new Blob(['ok']),
      filename: 'procurement.xlsx',
    })

    const { default: View } = await import('../ProcurementListView.vue')
    const wrapper = shallowMount(View, {
      props: {
        suggestion: makeSuggestion({ procurement_item_count: 3 }),
        items: [makeItem(1), makeItem(2), makeItem(3)],
      },
      global: { stubs: STUBS },
    })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      page: number
      pageSize: number
      pagedItems: SuggestionItem[]
      selectedIds: number[]
      selectedCount: number
      exportButtonLabel: string
      toggleSelectAll: (checked: boolean) => void
      handleExport: () => Promise<void>
    }

    vm.pageSize = 2
    await flushPromises()
    expect(vm.pagedItems.map((item) => item.id)).toEqual([1, 2])

    vm.toggleSelectAll(true)
    await flushPromises()
    expect(vm.selectedIds).toEqual([1, 2, 3])
    expect(vm.selectedCount).toBe(3)
    expect(vm.exportButtonLabel).toBe('导出采购单 Excel（3项）')

    vm.page = 2
    await flushPromises()
    expect(vm.pagedItems.map((item) => item.id)).toEqual([3])

    await vm.handleExport()
    expect(mockCreateProcurementSnapshot).toHaveBeenCalledWith(1, [1, 2, 3])
  })

  it('limits select-all to filtered rows and drops hidden selections', async () => {
    mockCreateProcurementSnapshot.mockResolvedValue({ id: 88 })
    mockDownloadSnapshotBlob.mockResolvedValue({
      blob: new Blob(['ok']),
      filename: 'procurement.xlsx',
    })

    const { default: View } = await import('../ProcurementListView.vue')
    const wrapper = shallowMount(View, {
      props: {
        suggestion: makeSuggestion({ procurement_item_count: 3 }),
        items: [makeItem(1), makeItem(2), makeItem(3)],
      },
      global: { stubs: STUBS },
    })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      skuFilter: string
      selectedIds: number[]
      selectedCount: number
      toggleSelectAll: (checked: boolean) => void
      handleExport: () => Promise<void>
    }

    vm.toggleSelectAll(true)
    vm.skuFilter = 'SKU-2'
    await flushPromises()
    expect(vm.selectedIds).toEqual([2])
    expect(vm.selectedCount).toBe(1)

    vm.toggleSelectAll(true)
    await flushPromises()
    expect(vm.selectedIds).toEqual([2])

    await vm.handleExport()
    expect(mockCreateProcurementSnapshot).toHaveBeenCalledWith(1, [2])
  })

  it('resets selection when suggestion changes', async () => {
    const { default: View } = await import('../ProcurementListView.vue')
    const wrapper = shallowMount(View, {
      props: {
        suggestion: makeSuggestion({ id: 1, procurement_item_count: 2 }),
        items: [makeItem(1), makeItem(2)],
      },
      global: { stubs: STUBS },
    })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      selectedIds: number[]
      toggleSelectAll: (checked: boolean) => void
    }

    vm.toggleSelectAll(true)
    await flushPromises()
    expect(vm.selectedIds).toEqual([1, 2])

    await wrapper.setProps({
      suggestion: makeSuggestion({ id: 2, procurement_item_count: 1 }),
      items: [makeItem(5)],
    })
    await flushPromises()

    expect(vm.selectedIds).toEqual([])
  })

  it('filters out rows without purchase quantity and sorts by sku', async () => {
    const { default: View } = await import('../ProcurementListView.vue')
    const wrapper = shallowMount(View, {
      props: {
        suggestion: makeSuggestion(),
        items: [
          makeItem(1, { purchase_qty: 0, commodity_sku: 'SKU-003' }),
          makeItem(2, { purchase_qty: 5, commodity_sku: 'SKU-002' }),
          makeItem(3, { purchase_qty: 6, commodity_sku: 'SKU-001' }),
        ],
      },
      global: { stubs: STUBS },
    })
    await flushPromises()

    const vm = wrapper.vm as unknown as { filteredItems: SuggestionItem[] }
    expect(vm.filteredItems.map((item) => item.id)).toEqual([3, 2])
  })

  it('shows calculation basis when snapshot exists', async () => {
    const { default: View } = await import('../ProcurementListView.vue')
    const wrapper = shallowMount(View, {
      props: {
        suggestion: makeSuggestion({ procurement_item_count: 1 }),
        items: [
          makeItem(1, {
            purchase_qty: 220,
            calculation_inputs_snapshot: {
              version: 1,
              generated_at: '2026-05-13T10:00:00+08:00',
              demand_date: '2026-05-13',
              target_days: 60,
              demand_days: 0,
              effective_target_days: 60,
              safety_stock_days: 15,
              purchase: {
                country_restock_qty_total: 100,
                country_restock_qty_by_country: { US: 100 },
                daily_velocity_total: 10,
                daily_velocity_by_country: { US: 10 },
                safety_stock_qty: 150,
                local_stock_available: 20,
                local_stock_reserved: 10,
                local_stock_total: 30,
                raw_purchase_qty: 220,
                final_purchase_qty: 220,
              },
              restock: { countries: {} },
            },
          }),
        ],
      },
      global: { stubs: STUBS },
    })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      isPurchaseAdjusted: (item: SuggestionItem) => boolean
      filteredItems: SuggestionItem[]
    }
    const item = vm.filteredItems[0]
    expect(vm.isPurchaseAdjusted(item)).toBe(false)
    expect(vm.isPurchaseAdjusted({ ...item, purchase_qty: 200 })).toBe(true)
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
