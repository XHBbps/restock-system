// @vitest-environment jsdom

import { readFileSync } from 'node:fs'

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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
  ElSelect: true,
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
        is_in_transit: true,
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

  it('renders the updated page title and table labels', async () => {
    mockListOutRecords.mockResolvedValue(buildResponse())

    const { default: View } = await import('../data/DataOutRecordsView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const html = wrapper.html()
    expect(html).toContain('出库记录')
    expect(html).toContain('出库单id')
    expect(html).toContain('出库仓库id')
    expect(html).toContain('更新时间')
    expect(html).toContain('出库单类型')

    const source = readFileSync('src/views/data/DataOutRecordsView.vue', 'utf-8')
    expect(source).toContain('出库单号')
    expect(source).toContain('商品id')
    expect(source).toContain('商品sku')
    expect(source).toContain('可用数')
    expect(source).toContain('采购单价')
  })
})
