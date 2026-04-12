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

vi.mock('@/stores/task', () => ({
  useTaskStore: () => ({
    tasksById: { 1: task },
    startPolling,
    stopPolling,
    isTerminal
  })
}))

describe('TaskProgress', () => {
  beforeEach(() => {
    startPolling.mockClear()
    stopPolling.mockClear()
    isTerminal.mockClear()
    isTerminal.mockReturnValue(false)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders task info and starts polling immediately', () => {
    const wrapper = shallowMount(TaskProgress, {
      props: { taskId: 1 },
      global: {
        stubs: {
          'el-card': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-progress': true
        }
      }
    })

    expect(wrapper.text()).toContain('sync_inventory')
    expect(wrapper.text()).toContain('运行中')
    expect(wrapper.text()).toContain('fetch')
    expect(startPolling).toHaveBeenCalledWith(1, expect.any(Function))
  })

  it('stops polling on unmount', () => {
    const wrapper = shallowMount(TaskProgress, {
      props: { taskId: 1 },
      global: {
        stubs: {
          'el-card': { template: '<div><slot /></div>' },
          'el-tag': { template: '<span><slot /></span>' },
          'el-progress': true
        }
      }
    })

    wrapper.unmount()

    expect(stopPolling).toHaveBeenCalledWith(1)
  })
})
