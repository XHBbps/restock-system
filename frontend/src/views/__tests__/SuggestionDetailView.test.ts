// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { SuggestionDetail, SuggestionItem } from '@/api/suggestion'

const mockGetSuggestion = vi.fn()
const mockPatchSuggestionItem = vi.fn()

vi.mock('@/api/suggestion', () => ({
  getSuggestion: (...args: unknown[]) => mockGetSuggestion(...args),
  patchSuggestionItem: (...args: unknown[]) => mockPatchSuggestionItem(...args),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' }, query: {} }),
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return { ...actual, ElMessage: { success: vi.fn(), error: vi.fn() } }
})

function makeItem(overrides: Partial<SuggestionItem> = {}): SuggestionItem {
  return {
    id: 10,
    commodity_sku: 'SKU-A',
    commodity_id: 'C001',
    commodity_name: 'Test Product',
    main_image: null,
    total_qty: 100,
    country_breakdown: { US: 60, JP: 40 },
    warehouse_breakdown: { US: { 'WH-1': 60 }, JP: { 'WH-2': 40 } },
    allocation_snapshot: null,
    velocity_snapshot: null,
    sale_days_snapshot: null,
    urgent: false,
    push_blocker: null,
    push_status: 'pending',
    saihu_po_number: null,
    push_error: null,
    push_attempt_count: 0,
    pushed_at: null,
    ...overrides,
  }
}

function makeSuggestion(
  overrides: Partial<SuggestionDetail> = {},
  itemOverrides: Partial<SuggestionItem> = {},
): SuggestionDetail {
  return {
    id: 1,
    status: 'draft',
    triggered_by: 'manual',
    total_items: 1,
    pushed_items: 0,
    failed_items: 0,
    global_config_snapshot: {},
    created_at: '2026-04-12T10:00:00',
    archived_at: null,
    items: [makeItem(itemOverrides)],
    ...overrides,
  }
}

const STUBS = {
  ElCard: { template: '<div><slot /><slot name="header" /></div>' },
  ElCollapse: { template: '<div><slot /></div>' },
  ElCollapseItem: { template: '<div><slot /><slot name="title" /></div>' },
  ElTag: { template: '<span><slot /></span>' },
  ElButton: true,
  ElInputNumber: true,
  ElDatePicker: true,
  ElTable: true,
  ElTableColumn: true,
  ElEmpty: true,
  SkuCard: true,
}

describe('SuggestionDetailView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('shows archived readonly tag when suggestion is archived', async () => {
    mockGetSuggestion.mockResolvedValue(makeSuggestion({ status: 'archived' }))

    const { default: View } = await import('../SuggestionDetailView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    expect(wrapper.html()).toContain('已归档建议单不可编辑')
  })

  it('shows pushed readonly tag when item is already pushed', async () => {
    mockGetSuggestion.mockResolvedValue(makeSuggestion({}, { push_status: 'pushed' }))

    const { default: View } = await import('../SuggestionDetailView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    expect(wrapper.html()).toContain('已推送条目不可编辑')
  })

  it('loads suggestion on mount via getSuggestion API', async () => {
    mockGetSuggestion.mockResolvedValue(makeSuggestion())

    const { default: View } = await import('../SuggestionDetailView.vue')
    shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    expect(mockGetSuggestion).toHaveBeenCalledWith(1)
  })

  it('submits edited quantity, country replenishment, warehouse and timing fields together', async () => {
    mockGetSuggestion.mockResolvedValueOnce(makeSuggestion()).mockResolvedValueOnce(makeSuggestion())
    mockPatchSuggestionItem.mockResolvedValue(makeItem())

    const { default: View } = await import('../SuggestionDetailView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      suggestion: SuggestionDetail
      editing: Record<
        number,
        {
          total_qty: number
          country_breakdown: Record<string, number>
          warehouse_breakdown: Record<string, Record<string, number>>
        }
      >
      save: (item: SuggestionItem) => Promise<void>
    }

    vm.editing[10].total_qty = 90
    vm.editing[10].country_breakdown = { US: 50, JP: 35 }
    vm.editing[10].warehouse_breakdown = { US: { 'WH-1': 50 }, JP: { 'WH-2': 35 } }

    await vm.save(vm.suggestion.items[0])

    expect(mockPatchSuggestionItem).toHaveBeenCalledWith(1, 10, {
      total_qty: 90,
      country_breakdown: { US: 50, JP: 35 },
      warehouse_breakdown: { US: { 'WH-1': 50 }, JP: { 'WH-2': 35 } },
    })
  })
})
