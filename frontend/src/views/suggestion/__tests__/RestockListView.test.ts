// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { SuggestionDetail, SuggestionItem } from '@/api/suggestion'

const mockCreateRestockSnapshot = vi.fn()
const mockDownloadSnapshotBlob = vi.fn()
const mockTriggerBlobDownload = vi.fn()
const mockListWarehouses = vi.fn()
const mockRecalculateSuggestionItem = vi.fn()
const mockConfirm = vi.fn()

vi.mock('@/api/config', async () => {
  const actual = await vi.importActual<typeof import('@/api/config')>('@/api/config')
  return {
    ...actual,
    listWarehouses: (...args: unknown[]) => mockListWarehouses(...args),
  }
})

vi.mock('@/api/snapshot', () => ({
  createRestockSnapshot: (...args: unknown[]) => mockCreateRestockSnapshot(...args),
  downloadSnapshotBlob: (...args: unknown[]) => mockDownloadSnapshotBlob(...args),
}))

vi.mock('@/api/suggestion', async () => {
  const actual = await vi.importActual<typeof import('@/api/suggestion')>('@/api/suggestion')
  return {
    ...actual,
    recalculateSuggestionItem: (...args: unknown[]) => mockRecalculateSuggestionItem(...args),
  }
})

vi.mock('@/utils/download', () => ({
  triggerBlobDownload: (...args: unknown[]) => mockTriggerBlobDownload(...args),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn() },
    ElMessageBox: { confirm: (...args: unknown[]) => mockConfirm(...args) },
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
  ElTooltip: { template: '<span><slot /></span>' },
  ElTable: { template: '<div><slot /></div>' },
  ElTableColumn: true,
  ElTag: { template: '<span><slot /></span>' },
  SkuCard: true,
}

describe('RestockListView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('selects all restock rows across pages and exports the global selection', async () => {
    mockListWarehouses.mockResolvedValue([])
    mockCreateRestockSnapshot.mockResolvedValue({ id: 99 })
    mockDownloadSnapshotBlob.mockResolvedValue({
      blob: new Blob(['ok']),
      filename: 'restock.xlsx',
    })

    const { default: View } = await import('../RestockListView.vue')
    const wrapper = shallowMount(View, {
      props: {
        suggestion: makeSuggestion({ restock_item_count: 3 }),
        items: [
          makeItem(1, { country_breakdown: { US: 10 } }),
          makeItem(2, { country_breakdown: { US: 8 } }),
          makeItem(3, { country_breakdown: { US: 6 } }),
        ],
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
    expect(vm.exportButtonLabel).toBe('导出补货单 Excel (3项)')

    vm.page = 2
    await flushPromises()
    expect(vm.pagedItems.map((item) => item.id)).toEqual([3])

    await vm.handleExport()
    expect(mockCreateRestockSnapshot).toHaveBeenCalledWith(1, [1, 2, 3])
    expect(mockConfirm).not.toHaveBeenCalled()
  })

  it('limits select-all to filtered rows and drops hidden selections', async () => {
    mockListWarehouses.mockResolvedValue([])
    mockCreateRestockSnapshot.mockResolvedValue({ id: 99 })
    mockDownloadSnapshotBlob.mockResolvedValue({
      blob: new Blob(['ok']),
      filename: 'restock.xlsx',
    })

    const { default: View } = await import('../RestockListView.vue')
    const wrapper = shallowMount(View, {
      props: {
        suggestion: makeSuggestion({ restock_item_count: 3 }),
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
    vm.skuFilter = 'SKU-3'
    await flushPromises()
    expect(vm.selectedIds).toEqual([3])
    expect(vm.selectedCount).toBe(1)

    vm.toggleSelectAll(true)
    await flushPromises()
    expect(vm.selectedIds).toEqual([3])

    await vm.handleExport()
    expect(mockCreateRestockSnapshot).toHaveBeenCalledWith(1, [3])
  })

  it('resets selection when suggestion changes', async () => {
    mockListWarehouses.mockResolvedValue([])

    const { default: View } = await import('../RestockListView.vue')
    const wrapper = shallowMount(View, {
      props: {
        suggestion: makeSuggestion({ id: 1, restock_item_count: 2 }),
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
      suggestion: makeSuggestion({ id: 2, restock_item_count: 1 }),
      items: [makeItem(7)],
    })
    await flushPromises()

    expect(vm.selectedIds).toEqual([])
  })

  it('renders only rows with positive country breakdown total', async () => {
    mockListWarehouses.mockResolvedValue([])

    const { default: View } = await import('../RestockListView.vue')
    const wrapper = shallowMount(View, {
      props: {
        suggestion: makeSuggestion(),
        items: [
          makeItem(1, { country_breakdown: { US: 10 } }),
          makeItem(2, { country_breakdown: { US: 0 } }),
        ],
      },
      global: { stubs: STUBS },
    })
    await flushPromises()

    const vm = wrapper.vm as unknown as { filteredItems: SuggestionItem[] }
    expect(vm.filteredItems.map((item) => item.id)).toEqual([1])
  })

  it('shows empty state when there is no restock demand', async () => {
    mockListWarehouses.mockResolvedValue([])

    const { default: View } = await import('../RestockListView.vue')
    const wrapper = shallowMount(View, {
      props: { suggestion: makeSuggestion({ restock_item_count: 0 }), items: [] },
      global: { stubs: STUBS },
    })

    expect(wrapper.findComponent({ name: 'ElEmpty' }).exists()).toBe(true)
  })

  it('exposes country-level restock quantities and warehouse allocations', async () => {
    mockListWarehouses.mockResolvedValue([])

    const { default: View } = await import('../RestockListView.vue')
    const wrapper = shallowMount(View, {
      props: {
        suggestion: makeSuggestion(),
        items: [
          makeItem(1, {
            country_breakdown: { US: 10, GB: 5 },
            warehouse_breakdown: { US: { 'WH-1': 10 }, GB: { 'WH-2': 5 } },
            restock_dates: { US: '2026-05-10', GB: '2026-05-01' },
          }),
        ],
      },
      global: { stubs: STUBS },
    })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      countryRows: (item: SuggestionItem) => {
        country: string
        qty: number
        warehouses: { id: string; qty: number }[]
      }[]
      filteredItems: SuggestionItem[]
    }
    const item = vm.filteredItems[0]
    expect(vm.countryRows(item).map((row) => [row.country, row.qty, row.warehouses])).toEqual([
      ['US', 10, [{ id: 'WH-1', qty: 10 }]],
      ['GB', 5, [{ id: 'WH-2', qty: 5 }]],
    ])
  })

  it('confirms before exporting rows with calculation warnings', async () => {
    mockListWarehouses.mockResolvedValue([])
    mockConfirm.mockResolvedValue('confirm')
    mockCreateRestockSnapshot.mockResolvedValue({ id: 99 })
    mockDownloadSnapshotBlob.mockResolvedValue({
      blob: new Blob(['ok']),
      filename: 'restock.xlsx',
    })

    const { default: View } = await import('../RestockListView.vue')
    const wrapper = shallowMount(View, {
      props: {
        suggestion: makeSuggestion({ restock_item_count: 1 }),
        items: [
          makeItem(1, {
            calculation_warnings: [
              {
                code: 'missing_velocity',
                country: 'UK',
                reason: 'missing_velocity',
                message: '缺少该国家的销量速度',
              },
            ],
          }),
        ],
      },
      global: { stubs: STUBS },
    })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      toggleSelectAll: (checked: boolean) => void
      handleExport: () => Promise<void>
    }
    vm.toggleSelectAll(true)
    await vm.handleExport()

    expect(mockConfirm).toHaveBeenCalled()
    expect(mockCreateRestockSnapshot).toHaveBeenCalledWith(1, [1])
  })

  it('recalculates one restock row and refreshes the parent', async () => {
    mockListWarehouses.mockResolvedValue([])
    mockRecalculateSuggestionItem.mockResolvedValue(makeItem(1))

    const { default: View } = await import('../RestockListView.vue')
    const wrapper = shallowMount(View, {
      props: {
        suggestion: makeSuggestion({ id: 5, restock_item_count: 1 }),
        items: [makeItem(1)],
      },
      global: { stubs: STUBS },
    })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      handleRecalculate: (item: SuggestionItem) => Promise<void>
      filteredItems: SuggestionItem[]
    }
    await vm.handleRecalculate(vm.filteredItems[0])

    expect(mockRecalculateSuggestionItem).toHaveBeenCalledWith(5, 1)
    expect(wrapper.emitted('refresh')).toBeTruthy()
  })
})
