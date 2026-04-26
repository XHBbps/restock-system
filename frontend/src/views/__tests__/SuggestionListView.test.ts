// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { SuggestionDetail } from '@/api/suggestion'
import { useAuthStore } from '@/stores/auth'

const mockGetCurrentSuggestion = vi.fn()
const mockDeleteSuggestion = vi.fn()
const mockGetGenerationToggle = vi.fn()
const mockPatchGenerationToggle = vi.fn()
const mockRunEngine = vi.fn()
const mockListTasks = vi.fn()
const mockConfirm = vi.fn()
const mockMessageSuccess = vi.fn()
const mockMessageError = vi.fn()
const mockMessageWarning = vi.fn()

vi.mock('@/api/suggestion', () => ({
  getCurrentSuggestion: (...args: unknown[]) => mockGetCurrentSuggestion(...args),
  deleteSuggestion: (...args: unknown[]) => mockDeleteSuggestion(...args),
}))

vi.mock('@/api/config', () => ({
  getGenerationToggle: (...args: unknown[]) => mockGetGenerationToggle(...args),
  patchGenerationToggle: (...args: unknown[]) => mockPatchGenerationToggle(...args),
}))

vi.mock('@/api/engine', () => ({
  runEngine: (...args: unknown[]) => mockRunEngine(...args),
}))

vi.mock('@/api/task', () => ({
  listTasks: (...args: unknown[]) => mockListTasks(...args),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: {
      success: (...args: unknown[]) => mockMessageSuccess(...args),
      error: (...args: unknown[]) => mockMessageError(...args),
      warning: (...args: unknown[]) => mockMessageWarning(...args),
    },
    ElMessageBox: {
      confirm: (...args: unknown[]) => mockConfirm(...args),
    },
  }
})

function makeSuggestion(): SuggestionDetail {
  return {
    id: 1,
    status: 'draft',
    triggered_by: 'manual',
    total_items: 2,
    procurement_item_count: 1,
    restock_item_count: 1,
    procurement_snapshot_count: 0,
    restock_snapshot_count: 0,
    archived_trigger: null,
    procurement_display_status: '未导出',
    restock_display_status: '未导出',
    procurement_display_status_code: 'pending',
    restock_display_status_code: 'pending',
    global_config_snapshot: { demand_date: '2026-04-30' },
    created_at: '2026-04-13T10:00:00',
    archived_at: null,
    items: [],
  }
}

function makeToggle(enabled = true) {
  return {
    enabled,
    updated_by: 1,
    updated_by_name: 'Tester',
    updated_at: '2026-04-19T10:00:00+08:00',
    can_enable: true,
    can_enable_reason: null,
  }
}

const STUBS = {
  PageSectionCard: {
    props: ['title'],
    template: '<div><h1>{{ title }}</h1><slot name="actions" /><slot /></div>',
  },
  TaskProgress: true,
  SuggestionTabBar: true,
  RouterView: {
    template: '<div class="router-view-stub" />',
  },
  ElEmpty: true,
  ElTag: { template: '<span><slot /></span>' },
  ElButton: {
    props: ['disabled', 'loading', 'title', 'type'],
    emits: ['click'],
    template: '<button :disabled="disabled" :title="title" @click="$emit(\'click\')"><slot /></button>',
  },
  ElDatePicker: {
    props: ['modelValue', 'disabled'],
    emits: ['update:modelValue'],
    template:
      '<input class="date-picker" :value="modelValue" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
}

async function mountView() {
  const { default: View } = await import('../SuggestionListView.vue')
  return shallowMount(View, { global: { stubs: STUBS } })
}

describe('SuggestionListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockConfirm.mockResolvedValue(undefined)
    mockGetCurrentSuggestion.mockResolvedValue(makeSuggestion())
    mockDeleteSuggestion.mockResolvedValue(undefined)
    mockGetGenerationToggle.mockResolvedValue(makeToggle())
    mockPatchGenerationToggle.mockResolvedValue(makeToggle(true))
    mockRunEngine.mockResolvedValue({ data: { task_id: 99, existing: false } })
    mockListTasks.mockResolvedValue({ items: [], total: 0 })

    const auth = useAuthStore()
    auth.setAuth('test-token', {
      id: 1,
      username: 'tester',
      displayName: 'Tester',
      roleName: 'Operator',
      isSuperadmin: false,
      passwordIsDefault: false,
      permissions: ['restock:operate'],
    })
  })

  it('loads current suggestion and generation toggle on mount', async () => {
    const wrapper = await mountView()
    await flushPromises()

    const vm = wrapper.vm as unknown as { suggestion: SuggestionDetail | null }
    expect(mockGetCurrentSuggestion).toHaveBeenCalled()
    expect(mockGetGenerationToggle).toHaveBeenCalled()
    expect(mockListTasks).toHaveBeenCalledWith({ job_name: 'calc_engine', status: 'pending', limit: 1 })
    expect(mockListTasks).toHaveBeenCalledWith({ job_name: 'calc_engine', status: 'running', limit: 1 })
    expect(vm.suggestion?.id).toBe(1)
  })

  it('validates demand date before calling engine', async () => {
    const wrapper = await mountView()
    await flushPromises()

    const generateButton = wrapper.findAll('button').find((item) => item.text().includes('生成采补建议'))
    await generateButton!.trigger('click')
    await flushPromises()

    expect(mockMessageWarning).toHaveBeenCalledWith('请选择补货日期')
    expect(mockRunEngine).not.toHaveBeenCalled()
  })

  it('runs engine with selected demand date', async () => {
    const wrapper = await mountView()
    await flushPromises()

    await wrapper.find('.date-picker').setValue('2099-04-30')
    const generateButton = wrapper.findAll('button').find((item) => item.text().includes('生成采补建议'))
    await generateButton!.trigger('click')
    await flushPromises()

    expect(mockRunEngine).toHaveBeenCalledWith({ demand_date: '2099-04-30' })
    expect(mockMessageSuccess).toHaveBeenCalledWith('规则引擎任务已入队')
  })

  it('rejects demand date before Beijing today', async () => {
    const wrapper = await mountView()
    await flushPromises()

    await wrapper.find('.date-picker').setValue('2000-01-01')
    const generateButton = wrapper.findAll('button').find((item) => item.text().includes('生成采补建议'))
    await generateButton!.trigger('click')
    await flushPromises()

    expect(mockMessageWarning).toHaveBeenCalledWith('补货日期不能早于今天')
    expect(mockRunEngine).not.toHaveBeenCalled()
  })

  it('reuses active engine task progress on mount', async () => {
    mockListTasks
      .mockResolvedValueOnce({ items: [], total: 0 })
      .mockResolvedValueOnce({
        items: [
          {
            id: 77,
            job_name: 'calc_engine',
            dedupe_key: 'calc_engine',
            status: 'running',
            trigger_source: 'manual',
            priority: 100,
            payload: {},
            current_step: null,
            step_detail: null,
            total_steps: null,
            attempt_count: 1,
            error_msg: null,
            result_summary: null,
            started_at: null,
            finished_at: null,
            created_at: '2026-04-24T10:00:00+08:00',
          },
        ],
        total: 1,
      })

    const wrapper = await mountView()
    await flushPromises()

    const vm = wrapper.vm as unknown as { genTaskId: number | null }
    expect(vm.genTaskId).toBe(77)
    expect(wrapper.find('.date-picker').attributes('disabled')).toBeDefined()
  })

  it('disables generate button when toggle is null', async () => {
    mockGetGenerationToggle.mockRejectedValue(new Error('forbidden'))

    const wrapper = await mountView()
    await flushPromises()

    const button = wrapper.findAll('button').find((item) => item.text().includes('生成采补建议'))
    expect(button?.attributes('disabled')).toBeDefined()
  })

  it('enables generation toggle after delete succeeds', async () => {
    mockGetCurrentSuggestion
      .mockResolvedValueOnce(makeSuggestion())
      .mockRejectedValueOnce({ response: { status: 404 } })
    mockGetGenerationToggle
      .mockResolvedValueOnce(makeToggle(false))
      .mockResolvedValueOnce(makeToggle(true))

    const wrapper = await mountView()
    await flushPromises()

    const deleteButton = wrapper.findAll('button').find((item) => item.text().includes('删除整单'))
    expect(deleteButton?.exists()).toBe(true)

    await deleteButton!.trigger('click')
    await flushPromises()

    expect(mockDeleteSuggestion).toHaveBeenCalledWith(1)
    expect(mockPatchGenerationToggle).toHaveBeenCalledWith(true)
    expect(mockDeleteSuggestion.mock.invocationCallOrder[0]).toBeLessThan(
      mockPatchGenerationToggle.mock.invocationCallOrder[0],
    )
    expect(mockGetCurrentSuggestion).toHaveBeenCalledTimes(2)
    expect(mockGetGenerationToggle).toHaveBeenCalledTimes(2)
    expect(mockMessageSuccess).toHaveBeenCalledWith('删除成功，已自动开启生成开关')
  })

  it('keeps deletion result when enabling toggle fails', async () => {
    mockGetCurrentSuggestion
      .mockResolvedValueOnce(makeSuggestion())
      .mockRejectedValueOnce({ response: { status: 404 } })
    mockGetGenerationToggle
      .mockResolvedValueOnce(makeToggle(false))
      .mockResolvedValueOnce(makeToggle(false))
    mockPatchGenerationToggle.mockRejectedValue({ response: { status: 403, data: {} } })

    const wrapper = await mountView()
    await flushPromises()

    const deleteButton = wrapper.findAll('button').find((item) => item.text().includes('删除整单'))
    await deleteButton!.trigger('click')
    await flushPromises()

    expect(mockDeleteSuggestion).toHaveBeenCalledWith(1)
    expect(mockPatchGenerationToggle).toHaveBeenCalledWith(true)
    expect(mockGetCurrentSuggestion).toHaveBeenCalledTimes(2)
    expect(mockGetGenerationToggle).toHaveBeenCalledTimes(2)
    expect(mockMessageWarning).toHaveBeenCalledWith(
      '删除成功，但开启生成开关失败，请前往全局参数手动开启',
    )
  })

  it('does not enable toggle when deletion fails', async () => {
    mockDeleteSuggestion.mockRejectedValue({ response: { status: 400, data: {} } })

    const wrapper = await mountView()
    await flushPromises()

    const deleteButton = wrapper.findAll('button').find((item) => item.text().includes('删除整单'))
    await deleteButton!.trigger('click')
    await flushPromises()

    expect(mockDeleteSuggestion).toHaveBeenCalledWith(1)
    expect(mockPatchGenerationToggle).not.toHaveBeenCalled()
    expect(mockGetCurrentSuggestion).toHaveBeenCalledTimes(1)
    expect(mockGetGenerationToggle).toHaveBeenCalledTimes(1)
    expect(mockMessageError).toHaveBeenCalledWith('删除失败')
  })
})
