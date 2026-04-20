// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { SuggestionDetail, SuggestionItem } from '@/api/suggestion'
import { useAuthStore } from '@/stores/auth'

const mockGetSuggestion = vi.fn()
const mockPatchSuggestionItem = vi.fn()
const mockListSnapshots = vi.fn()
const mockGetGenerationToggle = vi.fn()

vi.mock('@/api/suggestion', () => ({
  getSuggestion: (...args: unknown[]) => mockGetSuggestion(...args),
  patchSuggestionItem: (...args: unknown[]) => mockPatchSuggestionItem(...args),
}))

vi.mock('@/api/snapshot', () => ({
  createSnapshot: vi.fn(),
  downloadSnapshotBlob: vi.fn(),
  listSnapshots: (...args: unknown[]) => mockListSnapshots(...args),
}))

vi.mock('@/api/config', () => ({
  getGenerationToggle: (...args: unknown[]) => mockGetGenerationToggle(...args),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' }, query: {} }),
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn() },
    ElMessageBox: { confirm: vi.fn() },
  }
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
    export_status: 'pending',
    exported_snapshot_id: null,
    exported_at: null,
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
    snapshot_count: 0,
    global_config_snapshot: {},
    created_at: '2026-04-12T10:00:00',
    archived_at: null,
    items: [makeItem(itemOverrides)],
    ...overrides,
  }
}

const STUBS = {
  PageSectionCard: {
    props: ['title'],
    template: '<section><h2>{{ title }}</h2><slot /></section>',
  },
  ElCard: { template: '<div><slot name="header" /><slot /></div>' },
  ElCollapse: { template: '<div><slot /></div>' },
  ElCollapseItem: { template: '<div><slot name="title" /><slot /></div>' },
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
    mockListSnapshots.mockResolvedValue([])
    mockGetGenerationToggle.mockResolvedValue({
      enabled: true,
      updated_by: 1,
      updated_by_name: 'Tester',
      updated_at: '2026-04-19T10:00:00+08:00',
    })
    const auth = useAuthStore()
    auth.setAuth('test-token', {
      id: 1,
      username: 'tester',
      displayName: 'Tester',
      roleName: 'Operator',
      isSuperadmin: false,
      passwordIsDefault: false,
      permissions: ['restock:operate', 'restock:export'],
    })
  })

  it('shows archived readonly tag when suggestion is archived', async () => {
    mockGetSuggestion.mockResolvedValue(makeSuggestion({ status: 'archived' }))

    const { default: View } = await import('../SuggestionDetailView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    expect(wrapper.html()).toContain('不')
  })

  it('shows exported readonly tag when item is already exported', async () => {
    mockGetSuggestion.mockResolvedValue(makeSuggestion({}, { export_status: 'exported' }))

    const { default: View } = await import('../SuggestionDetailView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    expect(wrapper.html()).toContain('不')
  })

  it('loads suggestion, snapshots and generation toggle on mount', async () => {
    mockGetSuggestion.mockResolvedValue(makeSuggestion())

    const { default: View } = await import('../SuggestionDetailView.vue')
    shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    expect(mockGetSuggestion).toHaveBeenCalledWith(1)
    expect(mockListSnapshots).toHaveBeenCalledWith(1)
    expect(mockGetGenerationToggle).toHaveBeenCalled()
  })

  it('fails closed when export toggle status cannot be loaded', async () => {
    mockGetSuggestion.mockResolvedValue(makeSuggestion())
    mockGetGenerationToggle.mockRejectedValue(new Error('forbidden'))

    const { default: View } = await import('../SuggestionDetailView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      toggleEnabled: boolean
      toggleStateKnown: boolean
      exportButtonDisabled: boolean
    }
    expect(vm.toggleEnabled).toBe(false)
    expect(vm.toggleStateKnown).toBe(false)
    expect(vm.exportButtonDisabled).toBe(true)
  })

  it('submits edited quantity, country replenishment and warehouse fields together', async () => {
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
