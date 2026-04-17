// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const mockListSkuOverview = vi.fn()
const mockPatchSkuConfig = vi.fn()
const mockInitSkuConfigs = vi.fn()

vi.mock('@/api/data', () => ({
  listSkuOverview: (...args: unknown[]) => mockListSkuOverview(...args),
}))

vi.mock('@/api/config', () => ({
  patchSkuConfig: (...args: unknown[]) => mockPatchSkuConfig(...args),
  initSkuConfigs: (...args: unknown[]) => mockInitSkuConfigs(...args),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return { ...actual, ElMessage: { success: vi.fn(), error: vi.fn() } }
})

const STUBS = {
  PageSectionCard: {
    props: ['title'],
    template: '<div><h1>{{ title }}</h1><slot name="actions" /><slot /></div>',
  },
  TablePaginationBar: {
    props: ['currentPage', 'pageSize', 'total'],
    emits: ['update:currentPage', 'update:pageSize', 'current-change', 'size-change'],
    template: `
      <div class="pagination" :data-total="total">
        <button class="page-2" @click="$emit('update:currentPage', 2); $emit('current-change', 2)">page</button>
        <button class="size-100" @click="$emit('update:pageSize', 100); $emit('size-change', 100)">size</button>
      </div>
    `,
  },
  SkuCard: true,
  ElInput: {
    props: ['modelValue', 'placeholder'],
    emits: ['update:modelValue', 'keyup.enter', 'clear'],
    template: `
      <input
        :value="modelValue"
        :placeholder="placeholder"
        @input="$emit('update:modelValue', $event.target.value)"
        @keyup.enter="$emit('keyup.enter')"
      />
    `,
  },
  ElSelect: {
    props: ['modelValue', 'placeholder'],
    emits: ['update:modelValue', 'change'],
    template: `
      <div :data-placeholder="placeholder">
        <button class="enabled-true" @click="$emit('update:modelValue', true); $emit('change', true)">enabled</button>
      </div>
    `,
  },
  ElOption: true,
  ElButton: {
    emits: ['click'],
    template: '<button class="init" @click="$emit(\'click\')"><slot /></button>',
  },
  ElSwitch: true,
  ElTable: { template: '<div><slot /></div>' },
  ElTableColumn: { template: '<div><slot :row="{}" /></div>' },
  ElTag: { template: '<span><slot /></span>' },
}

function buildResponse(total = 88) {
  return {
    items: [
      {
        commodity_sku: 'SKU-1',
        commodity_name: 'Product',
        main_image: null,
        enabled: true,
        lead_time_days: 30,
        listing_count: 1,
        total_day30_sales: 10,
        listings: [],
      },
    ],
    total,
    page: 1,
    pageSize: 50,
  }
}

describe('DataProductsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockListSkuOverview.mockResolvedValue(buildResponse())
    mockPatchSkuConfig.mockResolvedValue({})
    mockInitSkuConfigs.mockResolvedValue({ created: 1, total: 2 })
  })

  it('loads SKU overview with backend pagination', async () => {
    const { default: View } = await import('../data/DataProductsView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS, directives: { loading: {} } } })
    await flushPromises()

    expect(wrapper.find('.pagination').attributes('data-total')).toBe('88')
    expect(mockListSkuOverview).toHaveBeenCalledWith({
      keyword: undefined,
      enabled: undefined,
      page: 1,
      page_size: 50,
    })
  })

  it('requests backend when pagination and filters change', async () => {
    const { default: View } = await import('../data/DataProductsView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS, directives: { loading: {} } } })
    await flushPromises()
    mockListSkuOverview.mockClear()

    await wrapper.find('.page-2').trigger('click')
    await flushPromises()
    expect(mockListSkuOverview).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, page_size: 50 }))

    await wrapper.find('.size-100').trigger('click')
    await flushPromises()
    expect(mockListSkuOverview).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, page_size: 100 }))

    await wrapper.find('.enabled-true').trigger('click')
    await flushPromises()
    expect(mockListSkuOverview).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, enabled: true }))
  })
})
