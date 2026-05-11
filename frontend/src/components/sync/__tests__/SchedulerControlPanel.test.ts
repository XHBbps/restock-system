// @vitest-environment jsdom

import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SchedulerControlPanel from '../SchedulerControlPanel.vue'

const STUBS = {
  StatusTag: true,
  ElSwitch: true,
  ElButton: { template: '<button type="button"><slot /></button>' },
}

describe('SchedulerControlPanel', () => {
  it('renders regular and order sync intervals separately', () => {
    const wrapper = shallowMount(SchedulerControlPanel, {
      props: {
        status: {
          enabled: true,
          running: true,
          timezone: 'Asia/Shanghai',
          sync_interval_minutes: 60,
          order_sync_interval_minutes: 120,
        },
        refreshing: false,
        toggleLoading: false,
      },
      global: { stubs: STUBS },
    })

    expect(wrapper.text()).toContain('60')
    expect(wrapper.text()).toContain('120')
    expect(wrapper.text()).toContain('补货计算：手动生成')
    expect(wrapper.text()).not.toContain('自动计算')
  })
})
