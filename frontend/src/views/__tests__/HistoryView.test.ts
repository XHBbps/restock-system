// @vitest-environment jsdom

import { readFileSync } from 'node:fs'

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { Suggestion } from '@/api/suggestion'

const mockListSuggestions = vi.fn()
const mockDeleteSuggestion = vi.fn()
const mockPush = vi.fn()
const mockConfirm = vi.fn()

vi.mock('@/api/suggestion', () => ({
  listSuggestions: (...args: unknown[]) => mockListSuggestions(...args),
  deleteSuggestion: (...args: unknown[]) => mockDeleteSuggestion(...args),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn() },
    ElMessageBox: { confirm: (...args: unknown[]) => mockConfirm(...args) },
  }
})

function makeSuggestion(overrides: Partial<Suggestion> = {}): Suggestion {
  return {
    id: 1,
    status: 'draft',
    triggered_by: 'manual',
    total_items: 10,
    snapshot_count: 0,
    global_config_snapshot: {},
    created_at: '2026-04-13T10:00:00',
    archived_at: null,
    ...overrides,
  }
}

const STUBS = {
  PageSectionCard: {
    props: ['title'],
    template: '<div><h1>{{ title }}</h1><slot name="actions" /><slot /></div>',
  },
  TablePaginationBar: true,
  ElInput: {
    props: ['modelValue', 'placeholder'],
    emits: ['update:modelValue', 'clear', 'keyup.enter'],
    template: '<input :value="modelValue" :placeholder="placeholder" />',
  },
  ElDatePicker: {
    props: ['modelValue', 'startPlaceholder', 'endPlaceholder'],
    template: '<div data-test="date-picker">{{ startPlaceholder }}-{{ endPlaceholder }}</div>',
  },
  ElSelect: {
    props: ['modelValue', 'placeholder'],
    template: '<div class="select-stub">{{ placeholder }}</div>',
  },
  ElOption: true,
  ElTag: { template: '<span><slot /></span>' },
  ElTable: { template: '<div><slot /></div>' },
  ElTableColumn: {
    props: ['label'],
    template: '<div><span>{{ label }}</span><slot :row="$attrs.row || {}" /></div>',
  },
  ElButton: {
    props: ['type'],
    emits: ['click'],
    template: '<button :data-type="type" @click="$emit(\'click\')"><slot /></button>',
  },
}

describe('HistoryView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads history suggestions on mount with backend pagination and default sort', async () => {
    mockListSuggestions.mockResolvedValue({ items: [makeSuggestion()], total: 1, page: 1, pageSize: 20 })

    const { default: View } = await import('../HistoryView.vue')
    shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    expect(mockListSuggestions).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 1,
        page_size: 20,
        sort_by: 'created_at',
        sort_order: 'desc',
      }),
    )
  })

  it('keeps filter controls ordered as sku, date range, then status', () => {
    const source = readFileSync('src/views/HistoryView.vue', 'utf-8')
    const skuIndex = source.indexOf('placeholder="SKU 关键字"')
    const dateIndex = source.indexOf('type="daterange"')
    const statusIndex = source.indexOf('placeholder="状态"')

    expect(skuIndex).toBeGreaterThan(-1)
    expect(dateIndex).toBeGreaterThan(skuIndex)
    expect(statusIndex).toBeGreaterThan(dateIndex)
  })

  it('status-filter dropdown offers 未提交 / 已导出 / 已归档 派生值', () => {
    const source = readFileSync('src/views/HistoryView.vue', 'utf-8')
    expect(source).toContain('value="pending"')
    expect(source).toContain('value="exported"')
    expect(source).toContain('value="archived"')
    expect(source).not.toContain('value="pushed"')
    expect(source).not.toContain('value="partial"')
    expect(source).not.toContain('value="draft"')
  })

  it('maps trigger source labels and only allows deleting rows without snapshots', async () => {
    mockListSuggestions.mockResolvedValue({ items: [makeSuggestion()], total: 1, page: 1, pageSize: 20 })

    const { default: View } = await import('../HistoryView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      triggeredByLabel: (triggeredBy: string) => string
      canDelete: (row: Suggestion) => boolean
    }

    expect(vm.triggeredByLabel('manual')).toBe('手动触发')
    expect(vm.triggeredByLabel('scheduler')).toBe('自动触发')
    expect(vm.triggeredByLabel('test-trigger')).toBe('test-trigger')
    expect(vm.canDelete(makeSuggestion({ snapshot_count: 0 }))).toBe(true)
    expect(vm.canDelete(makeSuggestion({ snapshot_count: 2 }))).toBe(false)
  })

  it('confirms deletion, deletes row and refreshes list', async () => {
    mockListSuggestions
      .mockResolvedValueOnce({ items: [makeSuggestion()], total: 1, page: 1, pageSize: 20 })
      .mockResolvedValueOnce({ items: [], total: 0, page: 1, pageSize: 20 })
    mockDeleteSuggestion.mockResolvedValue(undefined)
    mockConfirm.mockResolvedValue('confirm')

    const { default: View } = await import('../HistoryView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      remove: (row: Suggestion) => Promise<void>
    }

    await vm.remove(makeSuggestion({ id: 9, status: 'archived' }))

    expect(mockConfirm).toHaveBeenCalledWith(
      '确认删除建议单 #9 吗？删除后不可恢复。',
      '删除建议单',
      expect.objectContaining({
        type: 'warning',
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
      }),
    )
    expect(mockDeleteSuggestion).toHaveBeenCalledWith(9)
    expect(mockListSuggestions).toHaveBeenCalledTimes(2)
  })

  it('does not delete when confirmation is cancelled', async () => {
    mockListSuggestions.mockResolvedValue({ items: [makeSuggestion()], total: 1, page: 1, pageSize: 20 })
    mockConfirm.mockRejectedValue(new Error('cancel'))

    const { default: View } = await import('../HistoryView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      remove: (row: Suggestion) => Promise<void>
    }

    await vm.remove(makeSuggestion({ id: 5 }))

    expect(mockDeleteSuggestion).not.toHaveBeenCalled()
    expect(mockListSuggestions).toHaveBeenCalledTimes(1)
  })
})
