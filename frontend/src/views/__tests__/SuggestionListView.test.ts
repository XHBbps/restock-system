// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'

import type { SuggestionDetail, SuggestionItem } from '@/api/suggestion'

const mockGetCurrentSuggestion = vi.fn()

vi.mock('@/api/suggestion', () => ({
  getCurrentSuggestion: (...args: unknown[]) => mockGetCurrentSuggestion(...args),
}))

vi.mock('@/api/client', () => ({
  default: {
    post: vi.fn(),
  },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
    ElMessageBox: { confirm: vi.fn() },
  }
})

function makeItem(
  id: number,
  overrides: Partial<SuggestionItem> = {},
): SuggestionItem {
  return {
    id,
    commodity_sku: `SKU-${id}`,
    commodity_id: `CID-${id}`,
    commodity_name: `Product ${id}`,
    main_image: null,
    total_qty: 10,
    country_breakdown: { US: 10 },
    warehouse_breakdown: { US: { 'WH-1': 10 } },
    allocation_snapshot: null,
    velocity_snapshot: null,
    sale_days_snapshot: null,
    urgent: false,
    export_status: 'pending',
    exported_snapshot_id: null,
    exported_at: null,
    ...overrides,
  }
}

function makeSuggestion(): SuggestionDetail {
  return {
    id: 1,
    status: 'draft',
    triggered_by: 'manual',
    total_items: 4,
    snapshot_count: 0,
    global_config_snapshot: {},
    created_at: '2026-04-13T10:00:00',
    archived_at: null,
    items: [
      makeItem(1, { total_qty: 10, commodity_sku: 'SKU-ALPHA' }),
      makeItem(2, { total_qty: 30, commodity_sku: 'SKU-BETA' }),
      makeItem(3, { total_qty: 20, commodity_sku: 'SKU-GAMMA' }),
      makeItem(4, { total_qty: 5, commodity_sku: 'SKU-DELTA', urgent: true }),
    ],
  }
}

const STUBS = {
  PageSectionCard: {
    props: ['title'],
    template: '<div><h1>{{ title }}</h1><slot name="actions" /><slot /></div>',
  },
  TaskProgress: true,
  TablePaginationBar: true,
  ElEmpty: true,
  ElTag: { template: '<span><slot /></span>' },
  ElButton: true,
  ElInput: {
    props: ['modelValue', 'placeholder'],
    emits: ['update:modelValue'],
    template: '<input :value="modelValue" :placeholder="placeholder" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  ElSelect: true,
  ElOption: true,
  ElTable: defineComponent({
    props: ['data', 'rowKey', 'rowClassName'],
    emits: ['selectionChange', 'selectAll', 'sortChange'],
    setup(_, { slots, expose }) {
      expose({
        clearSelection: () => undefined,
        toggleRowSelection: () => undefined,
      })
      return () => h('div', slots.default?.())
    },
  }),
  ElTableColumn: true,
  ElTooltip: { template: '<div><slot /></div>' },
  SkuCard: {
    props: ['sku', 'name', 'image'],
    template: '<div class="sku-card-stub">{{ sku }}</div>',
  },
}

function createMountOptions() {
  return {
    global: {
      stubs: STUBS,
      directives: {
        loading: {
          mounted: () => undefined,
          updated: () => undefined,
        },
      },
    },
  }
}

describe('SuggestionListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renders the current suggestion items loaded from the API', async () => {
    mockGetCurrentSuggestion.mockResolvedValue(makeSuggestion())

    const { default: View } = await import('../SuggestionListView.vue')
    const wrapper = shallowMount(View, createMountOptions())
    await flushPromises()

    const vm = wrapper.vm as unknown as { filteredItems: SuggestionItem[] }
    expect(mockGetCurrentSuggestion).toHaveBeenCalled()
    expect(vm.filteredItems.map((item) => item.id)).toEqual([1, 2, 3, 4])
  })

  it('filters items by SKU keyword (case insensitive)', async () => {
    mockGetCurrentSuggestion.mockResolvedValue(makeSuggestion())

    const { default: View } = await import('../SuggestionListView.vue')
    const wrapper = shallowMount(View, createMountOptions())
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      searchSku: string
      filteredItems: SuggestionItem[]
    }

    vm.searchSku = 'beta'
    await flushPromises()

    expect(vm.filteredItems.map((item) => item.id)).toEqual([2])
  })

  it('supports sorting by total_qty via handleSortChange', async () => {
    mockGetCurrentSuggestion.mockResolvedValue(makeSuggestion())

    const { default: View } = await import('../SuggestionListView.vue')
    const wrapper = shallowMount(View, createMountOptions())
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      handleSortChange: (event: { prop: string; order: string | null }) => void
      pagedItems: SuggestionItem[]
    }

    vm.handleSortChange({ prop: 'total_qty', order: 'descending' })
    await flushPromises()

    expect(vm.pagedItems.map((item) => item.total_qty)).toEqual([30, 20, 10, 5])

    vm.handleSortChange({ prop: 'total_qty', order: 'ascending' })
    await flushPromises()

    expect(vm.pagedItems.map((item) => item.total_qty)).toEqual([5, 10, 20, 30])
  })

  it('paginates items according to pageSize and current page', async () => {
    mockGetCurrentSuggestion.mockResolvedValue(makeSuggestion())

    const { default: View } = await import('../SuggestionListView.vue')
    const wrapper = shallowMount(View, createMountOptions())
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      page: number
      pageSize: number
      pagedItems: SuggestionItem[]
    }

    vm.pageSize = 2
    await flushPromises()
    vm.page = 1
    await flushPromises()
    expect(vm.pagedItems).toHaveLength(2)
    // Default sort: urgent first (id=4), then by id ascending -> [4, 1, 2, 3]
    expect(vm.pagedItems.map((item) => item.id)).toEqual([4, 1])

    vm.page = 2
    await flushPromises()
    expect(vm.pagedItems).toHaveLength(2)
    expect(vm.pagedItems.map((item) => item.id)).toEqual([2, 3])
  })
})
