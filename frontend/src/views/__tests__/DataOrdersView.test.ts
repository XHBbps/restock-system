// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'

const mockListOrders = vi.fn()
const mockListDataShops = vi.fn()
const mockListOrderPlatforms = vi.fn()
const mockGetOrderDetail = vi.fn()
const mockUpdateOrderDetail = vi.fn()
const mockDownloadTemplate = vi.fn()
const mockPreviewOrderInfoMatch = vi.fn()
const mockApplyOrderInfoMatch = vi.fn()
const mockGetCountryOptions = vi.fn()
const mockHasPermission = vi.fn()
const mockMessageError = vi.fn()
const mockMessageSuccess = vi.fn()
const mockMessageInfo = vi.fn()
const mockTriggerBlobDownload = vi.fn()

vi.mock('@/api/data', () => ({
  listOrders: (...args: unknown[]) => mockListOrders(...args),
  listDataShops: (...args: unknown[]) => mockListDataShops(...args),
  listOrderPlatforms: (...args: unknown[]) => mockListOrderPlatforms(...args),
  getOrderDetail: (...args: unknown[]) => mockGetOrderDetail(...args),
  updateOrderDetail: (...args: unknown[]) => mockUpdateOrderDetail(...args),
  downloadOrderInfoMatchTemplate: (...args: unknown[]) => mockDownloadTemplate(...args),
  previewOrderInfoMatch: (...args: unknown[]) => mockPreviewOrderInfoMatch(...args),
  applyOrderInfoMatch: (...args: unknown[]) => mockApplyOrderInfoMatch(...args)
}))

vi.mock('@/api/config', () => ({
  getCountryOptions: (...args: unknown[]) => mockGetCountryOptions(...args)
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    hasPermission: (...args: unknown[]) => mockHasPermission(...args)
  })
}))

vi.mock('@/utils/download', () => ({
  triggerBlobDownload: (...args: unknown[]) => mockTriggerBlobDownload(...args)
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  return {
    ...actual,
    ElMessage: {
      error: (...args: unknown[]) => mockMessageError(...args),
      info: (...args: unknown[]) => mockMessageInfo(...args),
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
          v-if="placeholder === '平台'"
          type="button"
          class="platform-temu"
          @click="$emit('update:modelValue', 'Temu'); $emit('change', 'Temu')"
        >
          Temu
        </button>
        <button
          v-if="placeholder === '包裹状态'"
          type="button"
          class="status-shipped"
          @click="$emit('update:modelValue', 'has_shipped'); $emit('change', 'has_shipped')"
        >
          has_shipped
        </button>
        <slot />
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
    template: '<div><span>{{ label }}</span><slot name="default" :row="{}" /></div>'
  },
  ElTag: { template: '<span><slot /></span>' },
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  ElDialog: { template: '<div><slot /><slot name="footer" /></div>' },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { template: '<label><slot /></label>' },
  ElCheckboxGroup: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<div><slot /></div>'
  },
  ElCheckbox: {
    props: ['label'],
    template: '<label><input type="checkbox" :value="label" /> <slot /></label>'
  },
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

function buildOrderDetail(overrides: Record<string, unknown> = {}) {
  return {
    ...buildOrdersResponse().items[0],
    isBuyerRequestedCancel: false,
    items: [
      {
        orderItemId: 'ITEM-1',
        commoditySku: 'SKU-1',
        sellerSku: 'SELLER-SKU-1',
        quantityOrdered: 2,
        quantityShipped: 2,
        quantityUnfulfillable: 0,
        refundNum: 0,
        itemPriceCurrency: 'USD',
        itemPriceAmount: '10.00'
      }
    ],
    stateOrRegion: null,
    city: null,
    detailAddress: null,
    receiverName: null,
    detailFetchedAt: null,
    ...overrides
  }
}

describe('DataOrdersView', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    mockHasPermission.mockReturnValue(false)
    mockListOrders.mockResolvedValue(buildOrdersResponse())
    mockListDataShops.mockResolvedValue({
      items: [
        { id: 'SHOP-1', name: '店铺 1' },
        { id: 'SHOP-2', name: '店铺 2' }
      ],
      total: 2
    })
    mockListOrderPlatforms.mockResolvedValue(['Amazon', 'Temu'])
    mockGetCountryOptions.mockResolvedValue({
      items: [
        {
          code: 'US',
          label: 'US - 美国',
          builtin: true,
          observed: true,
          can_be_eu_member: true
        }
      ],
      unknown_country_codes: []
    })
    mockGetOrderDetail.mockResolvedValue(buildOrderDetail())
    mockUpdateOrderDetail.mockResolvedValue({})
    mockDownloadTemplate.mockResolvedValue(new Blob(['x']))
    mockPreviewOrderInfoMatch.mockResolvedValue({
      matchedOrderCount: 1,
      updateFields: ['国家'],
      errors: []
    })
    mockApplyOrderInfoMatch.mockResolvedValue({
      matchedOrderCount: 1,
      updateFields: ['国家'],
      errors: [],
      updatedOrderCount: 1
    })
  })

  it('loads current page from backend and fetches filter options separately', async () => {
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    expect(wrapper.find('.pagination').attributes('data-total')).toBe('188')
    expect(mockListDataShops).toHaveBeenCalledTimes(1)
    expect(mockListOrderPlatforms).toHaveBeenCalledTimes(1)
    expect(mockListOrders).toHaveBeenCalledWith({
      country: undefined,
      date_from: undefined,
      date_to: undefined,
      page: 1,
      page_size: 50,
      platform: undefined,
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

  it('keeps order list usable when platform options fail to load', async () => {
    mockListOrderPlatforms.mockRejectedValueOnce(new Error('boom'))
    const { default: View } = await import('../data/DataOrdersView.vue')
    shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    expect(mockListOrders).toHaveBeenCalled()
    expect(mockMessageError).not.toHaveBeenCalledWith(expect.stringContaining('平台'))
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

  it('resets to page 1 and passes platform when platform filter changes', async () => {
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    await wrapper.find('.page-3').trigger('click')
    await flushPromises()
    mockListOrders.mockClear()

    await wrapper.find('.platform-temu').trigger('click')
    await flushPromises()

    expect(mockListOrders).toHaveBeenLastCalledWith(
      expect.objectContaining({
        page: 1,
        platform: 'Temu'
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

  it('shows match and edit actions only with edit permission', async () => {
    const { default: View } = await import('../data/DataOrdersView.vue')

    const readonlyWrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()
    expect(readonlyWrapper.text()).not.toContain('信息匹配')

    mockHasPermission.mockReturnValue(true)
    const editableWrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()
    expect(editableWrapper.text()).toContain('信息匹配')
    expect(editableWrapper.text()).toContain('编辑')
  })

  it('downloads template with selected field keys', async () => {
    mockHasPermission.mockReturnValue(true)
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === '信息匹配')?.trigger('click')
    await wrapper.findAll('button').find((button) => button.text() === '导出空模板')?.trigger('click')
    await flushPromises()

    expect(mockDownloadTemplate).toHaveBeenCalledWith(
      expect.arrayContaining(['country_code', 'postal_code'])
    )
    expect(mockDownloadTemplate).not.toHaveBeenCalledWith(
      expect.arrayContaining(['marketplace_id', 'refund_status'])
    )
    expect(mockTriggerBlobDownload).toHaveBeenCalled()
  })

  it('uses validation wording and hides removed edit/import fields', async () => {
    mockHasPermission.mockReturnValue(true)
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    expect(wrapper.text()).toContain('导入校验')
    expect(wrapper.text()).toContain('校验')
    expect(wrapper.text()).not.toContain('导入预览')
    expect(wrapper.text()).not.toContain('Marketplace ID')
    expect(wrapper.text()).not.toContain('退款状态')
  })

  it('submits only changed postal code when editing order', async () => {
    mockHasPermission.mockReturnValue(true)
    mockGetOrderDetail.mockResolvedValue(buildOrderDetail({ postalCode: '' }))
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    await (wrapper.vm as unknown as { openEdit: (row: unknown) => Promise<void> }).openEdit(
      buildOrdersResponse().items[0]
    )
    await flushPromises()
    ;(wrapper.vm as unknown as { editForm: { postalCode: string } }).editForm.postalCode = '11'
    await (wrapper.vm as unknown as { saveEdit: () => Promise<void> }).saveEdit()
    await flushPromises()

    expect(mockUpdateOrderDetail).toHaveBeenCalledWith('SHOP-1', 'ORDER-1', 'PKG-1', {
      postalCode: '11'
    })
  })

  it('does not call update API when saving unchanged edit form', async () => {
    mockHasPermission.mockReturnValue(true)
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    await (wrapper.vm as unknown as { openEdit: (row: unknown) => Promise<void> }).openEdit(
      buildOrdersResponse().items[0]
    )
    await flushPromises()
    await (wrapper.vm as unknown as { saveEdit: () => Promise<void> }).saveEdit()
    await flushPromises()

    expect(mockUpdateOrderDetail).not.toHaveBeenCalled()
    expect(mockMessageInfo).toHaveBeenCalledWith('没有修改内容')
  })

  it('renders order detail content inside scoped template classes', async () => {
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    await (wrapper.vm as unknown as { openDetail: (row: unknown) => Promise<void> }).openDetail(
      buildOrdersResponse().items[0]
    )
    await flushPromises()

    expect(wrapper.find('.kv-grid').exists()).toBe(true)
    expect(wrapper.find('.detail-items-table').exists()).toBe(true)
    expect(wrapper.text()).toContain('订单商品ID')
  })

  it('uses custom file picker label and clears selected match file', async () => {
    mockHasPermission.mockReturnValue(true)
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    expect(wrapper.text()).toContain('选择文件')
    expect(wrapper.text()).toContain('未选择文件')

    const file = new File(['x'], 'orders.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    const input = wrapper.find<HTMLInputElement>('input[type="file"]')
    Object.defineProperty(input.element, 'files', {
      value: [file],
      configurable: true
    })
    await input.trigger('change')

    expect(wrapper.text()).toContain('orders.xlsx')
    await wrapper.findAll('button').find((button) => button.text() === 'x')?.trigger('click')

    expect(wrapper.text()).toContain('未选择文件')
    expect(wrapper.text()).not.toContain('orders.xlsx')
  })
})
