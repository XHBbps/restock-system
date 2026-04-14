// @vitest-environment jsdom

import { readFileSync } from 'node:fs'

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'

import type { SuggestionDetail, SuggestionItem } from '@/api/suggestion'

const mockGetCurrentSuggestion = vi.fn()
const mockPushItems = vi.fn()

vi.mock('@/api/suggestion', () => ({
  getCurrentSuggestion: (...args: unknown[]) => mockGetCurrentSuggestion(...args),
  pushItems: (...args: unknown[]) => mockPushItems(...args),
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

function makeItem(id: number, push_status: SuggestionItem['push_status'], push_blocker: string | null = null): SuggestionItem {
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
    push_blocker,
    push_status,
    saihu_po_number: null,
    push_error: null,
    push_attempt_count: 0,
    pushed_at: null,
  }
}

function makeSuggestion(): SuggestionDetail {
  return {
    id: 1,
    status: 'draft',
    triggered_by: 'manual',
    total_items: 4,
    pushed_items: 1,
    failed_items: 1,
    global_config_snapshot: {},
    created_at: '2026-04-13T10:00:00',
    archived_at: null,
    items: [
      makeItem(1, 'pending'),
      makeItem(2, 'blocked', 'missing_commodity_id'),
      makeItem(3, 'push_failed'),
      makeItem(4, 'pushed'),
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
    props: ['sku', 'name', 'image', 'blocker'],
    template: '<div class="sku-card-stub">{{ sku }}|{{ blocker ?? "none" }}</div>',
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

  it('keeps blocked items out of the pending filter', async () => {
    mockGetCurrentSuggestion.mockResolvedValue(makeSuggestion())

    const { default: View } = await import('../SuggestionListView.vue')
    const wrapper = shallowMount(View, createMountOptions())
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      filterPushStatus: string
      filteredItems: SuggestionItem[]
    }

    vm.filterPushStatus = 'pending'
    await flushPromises()

    expect(vm.filteredItems.map((item) => item.id)).toEqual([1])
  })

  it('supports filtering blocked items separately', async () => {
    mockGetCurrentSuggestion.mockResolvedValue(makeSuggestion())

    const { default: View } = await import('../SuggestionListView.vue')
    const wrapper = shallowMount(View, createMountOptions())
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      filterPushStatus: string
      filteredItems: SuggestionItem[]
    }

    vm.filterPushStatus = 'blocked'
    await flushPromises()

    expect(vm.filteredItems.map((item) => item.id)).toEqual([2])
  })

  it('does not pass blocker tags through the product card on suggestion list', async () => {
    mockGetCurrentSuggestion.mockResolvedValue(makeSuggestion())

    const { default: View } = await import('../SuggestionListView.vue')
    shallowMount(View, createMountOptions())
    await flushPromises()

    const source = readFileSync('src/views/SuggestionListView.vue', 'utf-8')
    expect(source).not.toContain(':blocker=')
    expect(source).toContain('value="blocked"')
  })
})
