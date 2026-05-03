// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'

const mockListOrders = vi.fn()
const mockListDataShops = vi.fn()
const mockGetOrderDetail = vi.fn()
const mockMessageError = vi.fn()
const mockMessageSuccess = vi.fn()

vi.mock('@/api/data', () => ({
  listOrders: (...args: unknown[]) => mockListOrders(...args),
  listDataShops: (...args: unknown[]) => mockListDataShops(...args),
  getOrderDetail: (...args: unknown[]) => mockGetOrderDetail(...args)
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  return {
    ...actual,
    ElMessage: {
      error: (...args: unknown[]) => mockMessageError(...args),
      success: (...args: unknown[]) => mockMessageSuccess(...args)
    }
  }
})

const STUBS = {
  PageSectionCard: {
    props: ['title'],
    template: '<div><h1>{{ title }}</h1><slot name="actions" /><slot /></div>'
  },
  TablePaginationBar: {
    props: ['currentPage', 'pageSize', 'total'],
    emits: ['update:currentPage', 'update:pageSize', 'current-change', 'size-change'],
    template: `
      <div class="pagination" :data-total="total">
        <button
          type="button"
          class="page-3"
          @click="$emit('update:currentPage', 3); $emit('current-change', 3)"
        >
          page-3
        </button>
        <button
          type="button"
          class="page-size-100"
          @click="$emit('update:pageSize', 100); $emit('size-change', 100)"
        >
          size-100
        </button>
      </div>
    `
  },
  ElInput: {
    props: ['modelValue', 'placeholder'],
    emits: ['update:modelValue', 'input', 'keyup.enter', 'clear'],
    template: `
      <div>
        <input
          :value="modelValue"
          :placeholder="placeholder"
          @input="$emit('update:modelValue', $event.target.value); $emit('input', $event.target.value)"
          @keyup.enter="$emit('keyup.enter')"
        />
        <button type="button" class="input-clear" @click="$emit('update:modelValue', ''); $emit('clear')">clear</button>
      </div>
    `
  },
  ElSelect: defineComponent({
    props: {
      modelValue: {
        type: String,
        default: ''
      },
      placeholder: {
        type: String,
        default: ''
      }
    },
    emits: ['update:modelValue', 'change', 'clear'],
    template: `
      <div :data-placeholder="placeholder">
        <button
          v-if="placeholder === '店铺'"
          type="button"
          class="shop-shop-2"
          @click="$emit('update:modelValue', 'SHOP-2'); $emit('change', 'SHOP-2')"
        >
          SHOP-2
        </button>
        <button
          v-if="placeholder === '国家'"
          type="button"
          class="country-us"
          @click="$emit('update:modelValue', 'US'); $emit('change', 'US')"
        >
          US
        </button>
        <button
          v-if="placeholder === '包裹状态'"
          type="button"
          class="status-shipped"
          @click="$emit('update:modelValue', 'has_shipped'); $emit('change', 'has_shipped')"
        >
          has_shipped
        </button>
      </div>
    `
  }),
  ElOption: true,
  ElDatePicker: {
    props: ['modelValue'],
    emits: ['update:modelValue', 'change'],
    template: `
      <button
        type="button"
        class="date-range"
        @click="$emit('update:modelValue', ['2026-04-01', '2026-04-15']); $emit('change', ['2026-04-01', '2026-04-15'])"
      >
        date
      </button>
    `
  },
  ElTable: { template: '<div><slot /></div>' },
  ElTableColumn: {
    props: ['label', 'prop'],
    template: '<div><span>{{ label }}</span></div>'
  },
  ElTag: { template: '<span><slot /></span>' },
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  ElDialog: { template: '<div><slot /></div>' },
  ElAlert: true,
  ElEmpty: true
}

const GLOBAL_CONFIG = {
  stubs: STUBS,
  directives: {
    loading: {}
  }
}

function buildOrdersResponse(
  overrides: Partial<{ total: number; page: number; pageSize: number }> = {}
) {
  return {
    items: [
      {
        shopId: 'SHOP-1',
        amazonOrderId: 'ORDER-1',
        orderPlatform: 'Amazon',
        packageSn: 'PKG-1',
        packageStatus: 'has_shipped',
        shopName: 'Main Shop',
        postalCode: '90210',
        marketplaceId: 'ATVPDKIKX0DER',
        countryCode: 'US',
        orderStatus: 'Shipped',
        orderTotalCurrency: 'USD',
        orderTotalAmount: '10.00',
        fulfillmentChannel: 'AFN',
        purchaseDate: '2026-04-16T10:00:00+08:00',
        lastUpdateDate: '2026-04-16T11:00:00+08:00',
        refundStatus: null,
        lastSyncAt: '2026-04-16T11:00:00+08:00',
        hasDetail: true,
        itemCount: 2
      }
    ],
    total: 188,
    page: 1,
    pageSize: 50,
    ...overrides
  }
}

describe('DataOrdersView', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    mockListOrders.mockResolvedValue(buildOrdersResponse())
    mockListDataShops.mockResolvedValue({
      items: [
        { id: 'SHOP-1', name: '店铺 1' },
        { id: 'SHOP-2', name: '店铺 2' }
      ],
      total: 2
    })
    mockGetOrderDetail.mockResolvedValue({})
  })

  it('loads current page from backend and fetches shop options separately', async () => {
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    expect(wrapper.find('.pagination').attributes('data-total')).toBe('188')
    expect(mockListDataShops).toHaveBeenCalledTimes(1)
    expect(mockListOrders).toHaveBeenCalledWith({
      country: undefined,
      date_from: undefined,
      date_to: undefined,
      page: 1,
      page_size: 50,
      shop_id: undefined,
      sku: undefined,
      sort_by: 'purchaseDate',
      sort_order: 'desc',
      status: undefined
    })
  })

  it('requests a new backend page when pagination changes', async () => {
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()
    mockListOrders.mockClear()

    await wrapper.find('.page-3').trigger('click')
    await flushPromises()

    expect(mockListOrders).toHaveBeenLastCalledWith(
      expect.objectContaining({
        page: 3,
        page_size: 50
      })
    )
  })

  it('resets to page 1 and passes shop_id when shop filter changes', async () => {
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    await wrapper.find('.page-3').trigger('click')
    await flushPromises()
    mockListOrders.mockClear()

    await wrapper.find('.shop-shop-2').trigger('click')
    await flushPromises()

    expect(mockListOrders).toHaveBeenLastCalledWith(
      expect.objectContaining({
        page: 1,
        shop_id: 'SHOP-2'
      })
    )
  })

  it('debounces sku search and supports immediate enter search', async () => {
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()
    mockListOrders.mockClear()

    const skuInput = wrapper.find('input[placeholder="SKU / 订单号"]')
    await skuInput.setValue('SKU-1')
    expect(mockListOrders).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(299)
    expect(mockListOrders).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    await flushPromises()
    expect(mockListOrders).toHaveBeenLastCalledWith(
      expect.objectContaining({
        page: 1,
        sku: 'SKU-1'
      })
    )

    mockListOrders.mockClear()
    await skuInput.setValue('SKU-2')
    await skuInput.trigger('keyup.enter')
    await flushPromises()

      expect(mockListOrders).toHaveBeenLastCalledWith(
      expect.objectContaining({
        page: 1,
        sku: 'SKU-2'
      })
    )
  })
})
