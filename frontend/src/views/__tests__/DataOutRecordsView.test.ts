// @vitest-environment jsdom

import { readFileSync } from 'node:fs'

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'

const mockListOutRecords = vi.fn()

vi.mock('@/api/data', () => ({
  listOutRecords: (...args: unknown[]) => mockListOutRecords(...args),
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
  TablePaginationBar: true,
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
  ElSelect: defineComponent({
    props: {
      modelValue: {
        type: [String, Boolean],
        default: undefined,
      },
      placeholder: {
        type: String,
        default: '',
      },
    },
    emits: ['update:modelValue', 'change', 'clear'],
    template: `
      <div :data-placeholder="placeholder">
        <button
          v-if="placeholder === '国家'"
          type="button"
          class="country-us"
          @click="$emit('update:modelValue', 'US'); $emit('change', 'US')"
        >
          US
        </button>
        <button
          v-if="placeholder === '状态'"
          type="button"
          class="status-true"
          @click="$emit('update:modelValue', true); $emit('change', true)"
        >
          true
        </button>
        <button
          v-if="placeholder === '状态'"
          type="button"
          class="status-false"
          @click="$emit('update:modelValue', false); $emit('change', false)"
        >
          false
        </button>
        <button
          type="button"
          class="select-clear"
          @click="$emit('update:modelValue', undefined); $emit('clear'); $emit('change', undefined)"
        >
          clear
        </button>
      </div>
    `,
  }),
  ElOption: true,
  ElTag: { template: '<span><slot /></span>' },
  ElTable: { template: '<div><slot /></div>' },
  ElTableColumn: {
    props: ['label', 'prop'],
    template: '<div><span>{{ label }}</span></div>',
  },
}

function buildResponse() {
  return {
    items: [
      {
        saihuOutRecordId: 'OUT-1',
        warehouseId: 'WH-1',
        outWarehouseNo: 'OW-1',
        targetWarehouseId: 'T-1',
        targetWarehouseName: 'Target',
        targetCountry: 'US',
        updateTime: '2026-04-14T10:00:00',
        type: 3,
        typeName: '调拨出库',
        remark: '在途中',
        status: '1',
        isInTransit: true,
        lastSeenAt: '2026-04-14T12:00:00',
        items: [
          {
            commodityId: 'CID-1',
            commoditySku: 'SKU-1',
            goods: 5,
            perPurchase: '12.50',
          },
        ],
      },
    ],
    total: 1,
    page: 1,
    pageSize: 5000,
  }
}

describe('DataOutRecordsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads out records with updateTime descending by default', async () => {
    mockListOutRecords.mockResolvedValue(buildResponse())

    const { default: View } = await import('../data/DataOutRecordsView.vue')
    shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    expect(mockListOutRecords).toHaveBeenCalledWith(
      expect.objectContaining({
        is_in_transit: undefined,
        sort_by: 'updateTime',
        sort_order: 'desc',
      }),
    )
  })

  it('passes outWarehouseNo filter when searching by out record number', async () => {
    mockListOutRecords.mockResolvedValue(buildResponse())

    const { default: View } = await import('../data/DataOutRecordsView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()
    mockListOutRecords.mockClear()

    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('OB2603260001')
    await inputs[0].trigger('keyup.enter')
    await flushPromises()

    expect(mockListOutRecords).toHaveBeenCalledWith(
      expect.objectContaining({
        out_warehouse_no: 'OB2603260001',
      }),
    )
  })

  it('allows selecting and clearing transit status filter', async () => {
    mockListOutRecords.mockResolvedValue(buildResponse())

    const { default: View } = await import('../data/DataOutRecordsView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()
    mockListOutRecords.mockClear()

    await wrapper.find('.status-true').trigger('click')
    await flushPromises()
    expect(mockListOutRecords).toHaveBeenLastCalledWith(
      expect.objectContaining({
        is_in_transit: true,
      }),
    )

    await wrapper.find('[data-placeholder="状态"] .select-clear').trigger('click')
    await flushPromises()
    expect(mockListOutRecords).toHaveBeenLastCalledWith(
      expect.objectContaining({
        is_in_transit: undefined,
      }),
    )
  })

  it('allows selecting and clearing country filter', async () => {
    mockListOutRecords.mockResolvedValue(buildResponse())

    const { default: View } = await import('../data/DataOutRecordsView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()
    mockListOutRecords.mockClear()

    await wrapper.find('.country-us').trigger('click')
    await flushPromises()
    expect(mockListOutRecords).toHaveBeenLastCalledWith(
      expect.objectContaining({
        country: 'US',
      }),
    )

    await wrapper.find('[data-placeholder="国家"] .select-clear').trigger('click')
    await flushPromises()
    expect(mockListOutRecords).toHaveBeenLastCalledWith(
      expect.objectContaining({
        country: undefined,
      }),
    )
  })

  it('renders the updated page title and detail columns', async () => {
    mockListOutRecords.mockResolvedValue(buildResponse())

    const { default: View } = await import('../data/DataOutRecordsView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const html = wrapper.html()
    expect(html).toContain('出库')
    expect(html).toContain('出库单id')
    expect(html).toContain('出库仓库id')
    expect(html).toContain('更新时间')
    expect(html).toContain('同步时间')
    expect(html).toContain('出库单类型')

    const source = readFileSync('src/views/data/DataOutRecordsView.vue', 'utf-8')
    expect(source).toContain('出库单号')
    expect(source).toContain('class="detail-table"')
    expect(source).toContain('clearable')
    expect(source).toContain('商品SKU')
    expect(source).toContain('商品ID')
    expect(source).toContain('可用数')
    expect(source).toContain('采购单价')
    expect(source).not.toContain('fixed="right"')
    expect(source.indexOf('商品SKU')).toBeLessThan(source.indexOf('商品ID'))
    expect(source.indexOf('商品ID')).toBeLessThan(source.indexOf('可用数'))
    expect(source.indexOf('可用数')).toBeLessThan(source.indexOf('采购单价'))
  })
})
