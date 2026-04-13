// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { refetchOrderDetail } from '@/api/sync'
import { ElMessage } from 'element-plus'

import OrderDetailFetchAction from './OrderDetailFetchAction.vue'

vi.mock('@/api/sync', () => ({
  refetchOrderDetail: vi.fn()
}))

describe('OrderDetailFetchAction', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('submits days payload and emits started task id', async () => {
    vi.mocked(refetchOrderDetail).mockResolvedValue({
      task_id: 12,
      existing: false,
      active_job_name: null,
      active_trigger_source: null,
      matched_count: 20,
      queued_count: 20
    })
    const success = vi.spyOn(ElMessage, 'success').mockImplementation(vi.fn())

    const wrapper = shallowMount(OrderDetailFetchAction, {
      global: {
        stubs: {
          'el-input-number': {
            props: ['modelValue'],
            emits: ['update:modelValue'],
            template: '<input />'
          },
          'el-button': {
            emits: ['click'],
            template: '<button @click="$emit(\'click\')"><slot /></button>'
          }
        }
      }
    })

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(refetchOrderDetail).toHaveBeenCalledWith({ days: 7 })
    expect(wrapper.emitted('started')).toEqual([[12]])
    expect(success).toHaveBeenCalledWith('详情获取任务已入队，共 20 条')
  })

  it('shows conflict message when reusing active sync task', async () => {
    vi.mocked(refetchOrderDetail).mockResolvedValue({
      task_id: 34,
      existing: true,
      active_job_name: 'sync_order_detail',
      active_trigger_source: 'scheduler',
      matched_count: 0,
      queued_count: 0
    })
    const warning = vi.spyOn(ElMessage, 'warning').mockImplementation(vi.fn())

    const wrapper = shallowMount(OrderDetailFetchAction, {
      global: {
        stubs: {
          'el-input-number': {
            props: ['modelValue'],
            emits: ['update:modelValue'],
            template: '<input />'
          },
          'el-button': {
            emits: ['click'],
            template: '<button @click="$emit(\'click\')"><slot /></button>'
          }
        }
      }
    })

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('started')).toEqual([[34]])
    expect(warning).toHaveBeenCalledWith('订单详情定时同步正在执行，当前复用其进度')
  })
})
