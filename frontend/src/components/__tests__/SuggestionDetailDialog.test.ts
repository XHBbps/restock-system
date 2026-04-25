// @vitest-environment jsdom

import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, inject, nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { SnapshotDetailOut, SnapshotItemOut, SnapshotOut, SnapshotType } from '@/api/snapshot'

const mockListWarehouses = vi.fn()
const mockListSnapshots = vi.fn()
const mockGetSnapshot = vi.fn()

vi.mock('@/api/config', () => ({
  listWarehouses: mockListWarehouses,
}))

vi.mock('@/api/snapshot', () => ({
  listSnapshots: mockListSnapshots,
  getSnapshot: mockGetSnapshot,
  downloadSnapshotBlob: vi.fn(),
}))

const ElDialogStub = defineComponent({
  name: 'ElDialogStub',
  inheritAttrs: false,
  template: `
    <div class="el-dialog-stub" v-bind="$attrs">
      <slot name="header" />
      <slot />
    </div>
  `,
})

const ElTableStub = defineComponent({
  name: 'ElTableStub',
  provide() {
    return {
      tableRow: Array.isArray(this.data) && this.data.length > 0 ? this.data[0] : {},
    }
  },
  inheritAttrs: false,
  props: {
    data: {
      type: Array,
      default: () => [],
    },
  },
  template: `
    <div
      class="el-table-stub"
      v-bind="$attrs"
      :data-size="data.length"
    >
      <slot />
    </div>
  `,
})

const ElTableColumnStub = defineComponent({
  name: 'ElTableColumnStub',
  setup() {
    const row = inject<Record<string, unknown>>('tableRow', {})
    return { row }
  },
  template: `
    <div class="el-table-column-stub">
      <slot v-if="$slots.default" :row="row" />
    </div>
  `,
})

const TablePaginationBarStub = defineComponent({
  name: 'TablePaginationBar',
  props: {
    currentPage: {
      type: Number,
      required: true,
    },
    pageSize: {
      type: Number,
      required: true,
    },
    total: {
      type: Number,
      required: true,
    },
    pageSizes: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['update:currentPage', 'update:pageSize', 'current-change', 'size-change'],
  template: `
    <div
      class="table-pagination-bar-stub"
      :data-current-page="currentPage"
      :data-page-size="pageSize"
      :data-total="total"
    >
      <button
        class="page-2-btn"
        @click="$emit('update:currentPage', 2); $emit('current-change', 2)"
      >
        page-2
      </button>
      <button
        class="page-size-20-btn"
        @click="$emit('update:pageSize', 20); $emit('size-change', 20)"
      >
        size-20
      </button>
    </div>
  `,
})

const STUBS = {
  ElDialog: ElDialogStub,
  ElButton: { template: '<button><slot /></button>' },
  ElTable: ElTableStub,
  ElTableColumn: ElTableColumnStub,
  ElTag: { template: '<span class="tag-stub"><slot /></span>' },
  SkuCard: { template: '<div class="sku-card-stub" />' },
  TablePaginationBar: TablePaginationBarStub,
  X: true,
}

function makeSnapshot(type: SnapshotType, id: number, version: number, items: SnapshotItemOut[]): SnapshotDetailOut {
  const base: SnapshotOut = {
    id,
    suggestion_id: 1,
    snapshot_type: type,
    version,
    note: null,
    exported_by: 7,
    exported_by_name: 'Tester',
    exported_at: '2026-04-24T09:00:00Z',
    item_count: items.length,
    generation_status: 'ready',
    file_size_bytes: 1024,
    download_count: 0,
  }
  return {
    ...base,
    items,
    global_config_snapshot: {},
  }
}

function makeSnapshotItem(index = 1, overrides: Partial<SnapshotItemOut> = {}): SnapshotItemOut {
  return {
    id: index,
    commodity_sku: `SKU-${String(index).padStart(3, '0')}`,
    commodity_name: `Demo ${index}`,
    main_image_url: null,
    total_qty: 15 + index,
    country_breakdown: { US: 10, GB: 5 },
    warehouse_breakdown: { US: { 'WH-1': 10 }, GB: { 'WH-2': 5 } },
    restock_dates: { US: '2026-05-10', GB: '2026-05-01' },
    purchase_qty: 8 + index,
    urgent: false,
    velocity_snapshot: null,
    sale_days_snapshot: null,
    ...overrides,
  }
}

function toSnapshotRow(snapshot: SnapshotDetailOut): SnapshotOut {
  const row = { ...snapshot }
  delete (row as Partial<SnapshotDetailOut>).items
  delete (row as Partial<SnapshotDetailOut>).global_config_snapshot
  return row
}

async function mountDialog(
  type: SnapshotType,
  snapshots = [makeSnapshot(type, 101, 3, [makeSnapshotItem()])],
) {
  mockListSnapshots.mockResolvedValue(snapshots.map(toSnapshotRow))
  mockGetSnapshot.mockImplementation(async (snapshotId: number) => {
    const snapshot = snapshots.find((item) => item.id === snapshotId)
    if (!snapshot) throw new Error(`snapshot ${snapshotId} not found`)
    return snapshot
  })

  const { default: View } = await import('../SuggestionDetailDialog.vue')
  const wrapper = mount(View, {
    props: {
      modelValue: true,
      suggestionId: 1,
      type,
    },
    global: { stubs: STUBS },
  })

  await flushPromises()
  return wrapper
}

describe('SuggestionDetailDialog', () => {
  beforeEach(() => {
    mockListWarehouses.mockReset()
    mockListSnapshots.mockReset()
    mockGetSnapshot.mockReset()
    mockListWarehouses.mockResolvedValue([])
  })

  it('computes snapshot country rows with quantities and warehouse allocations', async () => {
    const { default: View } = await import('../SuggestionDetailDialog.vue')
    const wrapper = mount(View, {
      props: {
        modelValue: false,
        suggestionId: 1,
        type: 'restock',
      },
      global: { stubs: STUBS },
    })

    const vm = wrapper.vm as unknown as {
      itemCountryRows: (item: SnapshotItemOut) => {
        country: string
        qty: number
        warehouses: { id: string; qty: number }[]
      }[]
    }
    const item = makeSnapshotItem()

    expect(vm.itemCountryRows(item).map((row) => [row.country, row.qty, row.warehouses])).toEqual([
      ['US', 10, [{ id: 'WH-1', qty: 10 }]],
      ['GB', 5, [{ id: 'WH-2', qty: 5 }]],
    ])
  })

  it('renders procurement pagination and only binds 10 items on first page', async () => {
    const snapshot = makeSnapshot(
      'procurement',
      101,
      3,
      Array.from({ length: 12 }, (_, index) => makeSnapshotItem(index + 1)),
    )
    const wrapper = await mountDialog('procurement', [snapshot])

    expect(mockListSnapshots).toHaveBeenCalledWith(1, 'procurement')
    expect(wrapper.find('.detail-table--procurement').attributes('data-size')).toBe('10')
    expect(wrapper.find('.table-pagination-bar-stub').exists()).toBe(true)
    expect(wrapper.find('.table-pagination-bar-stub').attributes('data-page-size')).toBe('10')
    expect(wrapper.find('.table-pagination-bar-stub').attributes('data-total')).toBe('12')
  })

  it('renders restock pagination and breakdown scroll wrapper inside dialog', async () => {
    const snapshot = makeSnapshot(
      'restock',
      101,
      3,
      Array.from({ length: 12 }, (_, index) => makeSnapshotItem(index + 1)),
    )
    const wrapper = await mountDialog('restock', [snapshot])

    expect(mockListSnapshots).toHaveBeenCalledWith(1, 'restock')
    expect(wrapper.find('.detail-table--restock').attributes('data-size')).toBe('10')
    expect(wrapper.find('.table-pagination-bar-stub').exists()).toBe(true)
    expect(wrapper.find('.breakdown-table-scroll').exists()).toBe(true)
  })

  it('uses centered empty-state dialog style when no snapshots exist', async () => {
    const wrapper = await mountDialog('restock', [])

    expect(wrapper.find('.el-dialog-stub').classes()).toContain('suggestion-detail-dialog--empty')
    expect(wrapper.find('.detail-main__empty').text()).toContain('选择左侧版本查看详情')
    expect(wrapper.find('.version-side__empty').text()).toContain('暂无快照版本')
    expect(wrapper.find('.table-pagination-bar-stub').exists()).toBe(false)
  })

  it('resets current page to first page when switching snapshot version', async () => {
    const latestSnapshot = makeSnapshot(
      'procurement',
      101,
      3,
      Array.from({ length: 12 }, (_, index) => makeSnapshotItem(index + 1)),
    )
    const olderSnapshot = makeSnapshot(
      'procurement',
      102,
      2,
      Array.from({ length: 18 }, (_, index) => makeSnapshotItem(index + 101)),
    )
    const wrapper = await mountDialog('procurement', [latestSnapshot, olderSnapshot])

    await wrapper.find('.page-2-btn').trigger('click')
    await nextTick()
    expect(wrapper.find('.table-pagination-bar-stub').attributes('data-current-page')).toBe('2')

    const versionButtons = wrapper.findAll('.version-item')
    expect(versionButtons).toHaveLength(2)

    await versionButtons[1].trigger('click')
    await flushPromises()

    expect(wrapper.find('.table-pagination-bar-stub').attributes('data-current-page')).toBe('1')
    expect(wrapper.find('.detail-table--procurement').attributes('data-size')).toBe('10')
    expect(mockGetSnapshot).toHaveBeenLastCalledWith(102)
  })

  it('resets current page when page size changes', async () => {
    const snapshot = makeSnapshot(
      'restock',
      101,
      3,
      Array.from({ length: 22 }, (_, index) => makeSnapshotItem(index + 1)),
    )
    const wrapper = await mountDialog('restock', [snapshot])

    await wrapper.find('.page-2-btn').trigger('click')
    await nextTick()
    expect(wrapper.find('.table-pagination-bar-stub').attributes('data-current-page')).toBe('2')

    await wrapper.find('.page-size-20-btn').trigger('click')
    await flushPromises()

    expect(wrapper.find('.table-pagination-bar-stub').attributes('data-current-page')).toBe('1')
    expect(wrapper.find('.table-pagination-bar-stub').attributes('data-page-size')).toBe('20')
    expect(wrapper.find('.detail-table--restock').attributes('data-size')).toBe('20')
  })
})
