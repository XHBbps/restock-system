// @vitest-environment jsdom

import { shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { TaskRun } from '@/api/task'
import TaskProgress from './TaskProgress.vue'

const startPolling = vi.fn()
const stopPolling = vi.fn()
const isTerminal = vi.fn(() => false)

const task: TaskRun = {
  id: 1,
  job_name: 'sync_inventory',
  dedupe_key: 'sync_inventory',
  status: 'running',
  trigger_source: 'manual',
  priority: 10,
  payload: {},
  current_step: 'fetch',
  step_detail: 'page 1',
  total_steps: 3,
  attempt_count: 1,
  error_msg: null,
  result_summary: null,
  started_at: '2026-04-09T00:00:00Z',
  finished_at: null,
  created_at: '2026-04-09T00:00:00Z'
}

const progressStub = {
  props: ['percentage', 'indeterminate', 'showText'],
  template:
    '<div class="el-progress-stub" :data-percentage="String(percentage)" :data-indeterminate="String(indeterminate)" />'
}

vi.mock('@/stores/task', () => ({
  useTaskStore: () => ({
    tasksById: { 1: task },
    startPolling,
    stopPolling,
    isTerminal
  })
}))

function mountComponent() {
  return shallowMount(TaskProgress, {
    props: { taskId: 1 },
    global: {
      stubs: {
        'el-card': { template: '<div><slot /></div>' },
        'el-tag': { template: '<span><slot /></span>' },
        'el-progress': progressStub
      }
    }
  })
}

describe('TaskProgress', () => {
  beforeEach(() => {
    startPolling.mockClear()
    stopPolling.mockClear()
    isTerminal.mockClear()
    isTerminal.mockReturnValue(false)
    task.status = 'running'
    task.current_step = 'fetch'
    task.step_detail = 'page 1'
    task.total_steps = 3
    task.error_msg = null
    task.result_summary = null
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders task info and starts polling immediately', () => {
    const wrapper = mountComponent()

    expect(wrapper.text()).toContain('sync_inventory')
    expect(wrapper.text()).toContain('运行中')
    expect(wrapper.text()).toContain('fetch')
    expect(startPolling).toHaveBeenCalledWith(1, expect.any(Function))
  })

  it('stops polling on unmount', () => {
    const wrapper = mountComponent()

    wrapper.unmount()

    expect(stopPolling).toHaveBeenCalledWith(1)
  })

  it('renders determinate percentage for count-based progress', () => {
    task.step_detail = '已完成 20 / 失败 5 / 总数 100'

    const wrapper = mountComponent()
    const progress = wrapper.get('.el-progress-stub')

    expect(progress.attributes('data-percentage')).toBe('25')
    expect(progress.attributes('data-indeterminate')).toBe('false')
  })

  it('renders determinate percentage for page-based progress', () => {
    task.step_detail = '第 2 / 5 页，当前页 100 条，已处理 100 条'

    const wrapper = mountComponent()
    const progress = wrapper.get('.el-progress-stub')

    expect(progress.attributes('data-percentage')).toBe('40')
    expect(progress.attributes('data-indeterminate')).toBe('false')
  })

  it('falls back to indeterminate progress for unparseable detail', () => {
    task.step_detail = '处理中'

    const wrapper = mountComponent()
    const progress = wrapper.get('.el-progress-stub')

    expect(progress.attributes('data-percentage')).toBe('50')
    expect(progress.attributes('data-indeterminate')).toBe('true')
  })
})
