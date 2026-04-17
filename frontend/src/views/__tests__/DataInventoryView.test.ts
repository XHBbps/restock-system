// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockListInventoryWarehouseGroups = vi.fn()

vi.mock('@/api/data', () => ({
  listInventoryWarehouseGroups: (...args: unknown[]) => mockListInventoryWarehouseGroups(...args),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return { ...actual, ElMessage: { error: vi.fn() } }
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
        <button class="size-50" @click="$emit('update:pageSize', 50); $emit('size-change', 50)">size</button>
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
        <button class="country-us" @click="$emit('update:modelValue', 'US'); $emit('change', 'US')">US</button>
      </div>
    `,
  },
  ElSwitch: {
    props: ['modelValue'],
    emits: ['update:modelValue', 'change'],
    template: '<button class="only-nonzero" @click="$emit(\'update:modelValue\', false); $emit(\'change\', false)">switch</button>',
  },
  ElOption: true,
  ElTable: { template: '<div><slot /></div>' },
  ElTableColumn: { template: '<div><slot :row=\"{}\" /></div>' },
  ElTag: { template: '<span><slot /></span>' },
}

function buildResponse(total = 23) {
  return {
    items: [
      {
        warehouseId: 'WH-1',
        warehouseName: 'Warehouse',
        warehouseType: 1,
        skuCount: 1,
        totalAvailable: 10,
        totalOccupy: 2,
        items: [
          {
            commoditySku: 'SKU-1',
            commodityName: 'Product',
            mainImage: null,
            warehouseId: 'WH-1',
            warehouseName: 'Warehouse',
            warehouseType: 1,
            country: 'US',
            stockAvailable: 10,
            stockOccupy: 2,
            updatedAt: '2026-04-17T10:00:00',
          },
        ],
      },
    ],
    total,
    page: 1,
    pageSize: 20,
  }
}

describe('DataInventoryView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListInventoryWarehouseGroups.mockResolvedValue(buildResponse())
  })

  it('loads warehouse groups from backend', async () => {
    const { default: View } = await import('../data/DataInventoryView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS, directives: { loading: {} } } })
    await flushPromises()

    expect(wrapper.find('.pagination').attributes('data-total')).toBe('23')
    expect(mockListInventoryWarehouseGroups).toHaveBeenCalledWith({
      sku: undefined,
      country: undefined,
      only_nonzero: true,
      page: 1,
      page_size: 20,
    })
  })

  it('requests backend pages and resets filters to first page', async () => {
    const { default: View } = await import('../data/DataInventoryView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS, directives: { loading: {} } } })
    await flushPromises()
    mockListInventoryWarehouseGroups.mockClear()

    await wrapper.find('.page-2').trigger('click')
    await flushPromises()
    expect(mockListInventoryWarehouseGroups).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }))

    await wrapper.find('.country-us').trigger('click')
    await flushPromises()
    expect(mockListInventoryWarehouseGroups).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, country: 'US' }))
  })
})
