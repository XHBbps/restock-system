// @vitest-environment jsdom

import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

const STUBS = {
  PageSectionCard: {
    props: ['title'],
    template: '<div><h1>{{ title }}</h1><slot /></div>',
  },
  SuggestionTabBar: true,
  RouterView: { template: '<div class="router-view-stub" />' },
}

describe('HistoryView', () => {
  it('renders as a history container with child route outlet', async () => {
    const { default: View } = await import('../HistoryView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })

    expect(wrapper.text()).toContain('历史记录')
    expect(wrapper.find('.router-view-stub').exists()).toBe(true)
  })
})
