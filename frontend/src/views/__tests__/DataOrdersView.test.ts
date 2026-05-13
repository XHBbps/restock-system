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
const mockDownloadErrorReport = vi.fn()
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
  downloadOrderInfoMatchErrorReport: (...args: unknown[]) => mockDownloadErrorReport(...args),
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
  MobileRecordList: {
    props: ['items'],
    template: `
      <div class="mobile-record-list">
        <div v-for="(item, index) in items" :key="index">
          <slot :item="item" />
        </div>
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
  ElTable: {
    props: ['data'],
    template: `
      <div>
        <slot />
        <div v-for="(row, index) in data" :key="index" class="table-row">
          {{ row.row }} {{ row.field }} {{ row.message }}
        </div>
      </div>
    `
  },
  ElTableColumn: {
    props: ['label', 'prop'],
    template: '<div><span>{{ label }}</span><slot name="default" :row="{}" /></div>'
  },
  ElTag: { template: '<span><slot /></span>' },
  ElButton: {
    props: ['disabled', 'loading'],
    template: '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>'
  },
  ElDialog: { template: '<div><slot /><slot name="footer" /></div>' },
  ElDrawer: {
    props: ['modelValue'],
    template: '<div v-if="modelValue" class="drawer"><slot /><slot name="footer" /></div>'
  },
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

function setViewportWidth(width: number) {
  Object.defineProperty(window, 'innerWidth', {
    configurable: true,
    writable: true,
    value: width
  })
  window.dispatchEvent(new Event('resize'))
}

function buildOrdersResponse(
  overrides: Partial<{ total: number; page: number; pageSize: number }> = {},
  itemOverrides: Record<string, unknown> = {}
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
        itemCount: 2,
        ...itemOverrides
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
    setViewportWidth(1024)
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
    mockDownloadErrorReport.mockResolvedValue(new Blob(['errors']))
    mockPreviewOrderInfoMatch.mockResolvedValue({
      matchedOrderCount: 1,
      matchedOrderIds: ['ORDER-1'],
      updateFields: ['国家'],
      errors: []
    })
    mockApplyOrderInfoMatch.mockResolvedValue({
      matchedOrderCount: 1,
      matchedOrderIds: ['ORDER-1'],
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

  it('renders local purchase date in mobile order cards', async () => {
    setViewportWidth(375)
    mockListOrders.mockResolvedValue(
      buildOrdersResponse({}, { purchaseDateLocal: '2026-04-15T19:00:00-07:00' })
    )
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    expect(wrapper.text()).toContain('2026-04-15 19:00')
    expect(wrapper.text()).not.toContain('2026-04-16 10:00')
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

    expect(mockDownloadTemplate).toHaveBeenCalledWith(['country_code', 'postal_code'])
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
    const matchFieldText = wrapper.find('.field-grid').text()
    expect(matchFieldText).toContain('国家')
    expect(matchFieldText).toContain('邮编')
    expect(matchFieldText).not.toContain('店铺名称')
    expect(matchFieldText).not.toContain('平台')
    expect(matchFieldText).not.toContain('订单金额')
    expect(matchFieldText).not.toContain('币种')
    expect(matchFieldText).not.toContain('履约渠道')
    expect(matchFieldText).not.toContain('下单时间')
    expect(matchFieldText).not.toContain('最后更新时间')

    await (wrapper.vm as unknown as { openEdit: (row: unknown) => Promise<void> }).openEdit(
      buildOrdersResponse().items[0]
    )
    await flushPromises()
    expect(
      Object.keys(
        (wrapper.vm as unknown as { editForm: Record<string, string> }).editForm
      ).sort()
    ).toEqual(['countryCode', 'postalCode'])
  })

  it('renders compact successful match validation result and enables apply', async () => {
    mockHasPermission.mockReturnValue(true)
    mockPreviewOrderInfoMatch.mockReset()
    mockPreviewOrderInfoMatch.mockResolvedValueOnce({
      matchedOrderCount: 1,
      matchedOrderIds: ['ORDER-1'],
      updateFields: ['国家', '邮编'],
      errors: []
    })
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    const applyButton = wrapper.findAll('button').find((button) => button.text() === '确认导入')
    expect(applyButton?.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).not.toContain('校验通过，可以确认导入')

    const file = new File(['x'], 'orders.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    const input = wrapper.find<HTMLInputElement>('input[type="file"]')
    Object.defineProperty(input.element, 'files', {
      value: [file],
      configurable: true
    })
    await input.trigger('change')
    await (wrapper.vm as unknown as { previewMatch: () => Promise<void> }).previewMatch()
    await flushPromises()

    expect(wrapper.text()).toContain('校验通过，可以确认导入')
    expect(wrapper.text()).toContain('ORDER-1')
    expect(wrapper.text()).toContain('国家')
    expect(wrapper.text()).toContain('邮编')
    expect(wrapper.text()).toContain('邮编校验通过，空值将清空原邮编')
    expect(wrapper.text()).not.toContain('下载错误文件')
    expect(
      wrapper.findAll('button').find((button) => button.text() === '确认导入')?.attributes('disabled')
    ).toBeUndefined()
  })

  it('renders failed match validation result and keeps apply disabled', async () => {
    mockHasPermission.mockReturnValue(true)
    mockPreviewOrderInfoMatch.mockReset()
    mockPreviewOrderInfoMatch.mockResolvedValueOnce({
      matchedOrderCount: 0,
      matchedOrderIds: [],
      updateFields: ['国家'],
      errors: [{ row: 2, field: '订单号', message: '订单号不存在' }]
    })
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    const file = new File(['x'], 'orders.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    const input = wrapper.find<HTMLInputElement>('input[type="file"]')
    Object.defineProperty(input.element, 'files', {
      value: [file],
      configurable: true
    })
    await input.trigger('change')
    await (wrapper.vm as unknown as { previewMatch: () => Promise<void> }).previewMatch()
    await flushPromises()

    expect(wrapper.text()).toContain('校验未通过')
    expect(wrapper.text()).toContain('错误数量：1')
    expect(wrapper.text()).toContain('订单号不存在')
    expect(wrapper.text()).toContain('下载错误文件')
    expect(wrapper.text()).not.toContain('校验通过，可以确认导入')
    expect(
      wrapper.findAll('button').find((button) => button.text() === '确认导入')?.attributes('disabled')
    ).toBeDefined()
  })

  it('downloads failed match error workbook with current file and field keys', async () => {
    mockHasPermission.mockReturnValue(true)
    mockPreviewOrderInfoMatch.mockReset()
    mockPreviewOrderInfoMatch.mockResolvedValueOnce({
      matchedOrderCount: 0,
      matchedOrderIds: [],
      updateFields: ['国家'],
      errors: [{ row: 2, field: '订单号', message: '订单号不存在' }]
    })
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    const file = new File(['x'], 'orders.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    const input = wrapper.find<HTMLInputElement>('input[type="file"]')
    Object.defineProperty(input.element, 'files', {
      value: [file],
      configurable: true
    })
    await input.trigger('change')
    await (wrapper.vm as unknown as { previewMatch: () => Promise<void> }).previewMatch()
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === '下载错误文件')?.trigger('click')
    await flushPromises()

    expect(mockDownloadErrorReport).toHaveBeenCalledWith(file, ['country_code', 'postal_code'])
    expect(mockTriggerBlobDownload).toHaveBeenCalledWith(
      expect.any(Blob),
      '订单信息匹配错误原因.xlsx'
    )
    expect(
      wrapper.findAll('button').find((button) => button.text() === '确认导入')?.attributes('disabled')
    ).toBeDefined()
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

  it('submits only changed country when editing order', async () => {
    mockHasPermission.mockReturnValue(true)
    mockGetOrderDetail.mockResolvedValue(buildOrderDetail({ countryCode: 'US' }))
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    await (wrapper.vm as unknown as { openEdit: (row: unknown) => Promise<void> }).openEdit(
      buildOrdersResponse().items[0]
    )
    await flushPromises()
    ;(wrapper.vm as unknown as { editForm: { countryCode: string } }).editForm.countryCode = 'CA'
    await (wrapper.vm as unknown as { saveEdit: () => Promise<void> }).saveEdit()
    await flushPromises()

    expect(mockUpdateOrderDetail).toHaveBeenCalledWith('SHOP-1', 'ORDER-1', 'PKG-1', {
      countryCode: 'CA'
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

  it('renders local order timestamps in detail dialog and falls back to legacy fields', async () => {
    mockGetOrderDetail.mockResolvedValueOnce(
      buildOrderDetail({
        purchaseDateLocal: '2026-04-15T19:00:00-07:00',
        lastUpdateDateLocal: '2026-04-15T20:00:00-07:00'
      })
    )
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    await (wrapper.vm as unknown as { openDetail: (row: unknown) => Promise<void> }).openDetail(
      buildOrdersResponse().items[0]
    )
    await flushPromises()

    expect(wrapper.text()).toContain('2026-04-15 19:00')
    expect(wrapper.text()).toContain('2026-04-15 20:00')
    expect(wrapper.text()).not.toContain('2026-04-16 10:00')
    expect(wrapper.text()).not.toContain('2026-04-16 11:00')

    mockGetOrderDetail.mockResolvedValueOnce(buildOrderDetail())
    await (wrapper.vm as unknown as { openDetail: (row: unknown) => Promise<void> }).openDetail(
      buildOrdersResponse().items[0]
    )
    await flushPromises()

    expect(wrapper.text()).toContain('2026-04-16 10:00')
    expect(wrapper.text()).toContain('2026-04-16 11:00')
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

  it('renders compact mobile filters and fixed mobile pagination without desktop pagination', async () => {
    setViewportWidth(375)
    mockHasPermission.mockReturnValue(true)
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    expect(wrapper.find('.mobile-order-actions').exists()).toBe(true)
    expect(wrapper.find('input[placeholder="SKU / 订单号"]').exists()).toBe(true)
    expect(wrapper.find('.mobile-filter-trigger').text()).toContain('筛选')
    expect(wrapper.text()).toContain('信息匹配')
    expect(wrapper.find('.desktop-order-filters').exists()).toBe(false)
    expect(wrapper.find('.pagination').exists()).toBe(false)
    expect(wrapper.find('.mobile-fixed-pagination').exists()).toBe(true)
    expect(wrapper.find('.mobile-page-indicator').text()).toBe('第 1 / 4 页')
  })

  it('opens mobile filter drawer and applies backend filters from drawer controls', async () => {
    setViewportWidth(375)
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()
    mockListOrders.mockClear()

    await wrapper.find('.mobile-filter-trigger').trigger('click')
    await wrapper.find('.country-us').trigger('click')
    await flushPromises()
    expect(mockListOrders).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, country: 'US' }))

    await wrapper.find('.shop-shop-2').trigger('click')
    await flushPromises()
    expect(mockListOrders).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, shop_id: 'SHOP-2' }))

    await wrapper.find('.platform-temu').trigger('click')
    await flushPromises()
    expect(mockListOrders).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, platform: 'Temu' }))

    await wrapper.find('.status-shipped').trigger('click')
    await flushPromises()
    expect(mockListOrders).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, status: 'has_shipped' })
    )

    await wrapper.find('.date-range').trigger('click')
    await flushPromises()
    expect(mockListOrders).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, date_from: '2026-04-01', date_to: '2026-04-15' })
    )
  })

  it('resets mobile filters and reloads the first page', async () => {
    setViewportWidth(375)
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()

    await wrapper.find('input[placeholder="SKU / 订单号"]').setValue('SKU-1')
    await vi.advanceTimersByTimeAsync(300)
    await wrapper.find('.mobile-filter-trigger').trigger('click')
    await wrapper.find('.country-us').trigger('click')
    await flushPromises()
    mockListOrders.mockClear()

    await wrapper.findAll('button').find((button) => button.text() === '重置筛选')?.trigger('click')
    await flushPromises()

    expect(mockListOrders).toHaveBeenLastCalledWith(
      expect.objectContaining({
        country: undefined,
        date_from: undefined,
        date_to: undefined,
        page: 1,
        sku: undefined
      })
    )
  })

  it('uses the mobile fixed pagination buttons with boundary disabled states', async () => {
    setViewportWidth(375)
    mockListOrders.mockResolvedValue(buildOrdersResponse({ total: 60 }))
    const { default: View } = await import('../data/DataOrdersView.vue')
    const wrapper = shallowMount(View, { global: GLOBAL_CONFIG })
    await flushPromises()
    mockListOrders.mockClear()

    expect(wrapper.find('.mobile-page-prev').attributes('disabled')).toBeDefined()
    expect(wrapper.find('.mobile-page-next').attributes('disabled')).toBeUndefined()

    await wrapper.find('.mobile-page-next').trigger('click')
    await flushPromises()

    expect(mockListOrders).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }))
    expect(wrapper.find('.mobile-page-indicator').text()).toBe('第 2 / 2 页')
    expect(wrapper.find('.mobile-page-next').attributes('disabled')).toBeDefined()
  })
})
