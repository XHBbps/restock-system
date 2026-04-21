// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { SuggestionDetail } from '@/api/suggestion'

const mockGetSuggestion = vi.fn()
const mockPush = vi.fn()
const mockBack = vi.fn()

vi.mock('@/api/suggestion', () => ({
  getSuggestion: (...args: unknown[]) => mockGetSuggestion(...args),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '9' } }),
  useRouter: () => ({ push: mockPush, back: mockBack }),
}))

function makeSuggestion(): SuggestionDetail {
  return {
    id: 9,
    status: 'draft',
    triggered_by: 'manual',
    total_items: 0,
    procurement_item_count: 0,
    restock_item_count: 0,
    procurement_snapshot_count: 0,
    restock_snapshot_count: 0,
    global_config_snapshot: {},
    created_at: '2026-04-21T10:00:00',
    archived_at: null,
    items: [],
  }
}

const STUBS = {
  PageSectionCard: {
    props: ['title'],
    template: '<div><h1>{{ title }}</h1><slot name="actions" /><slot /></div>',
  },
  SuggestionTabBar: true,
  RouterView: { template: '<div class="router-view-stub" />' },
  ElTag: { template: '<span><slot /></span>' },
  ElButton: true,
  ElEmpty: true,
}

describe('SuggestionDetailView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetSuggestion.mockResolvedValue(makeSuggestion())
  })

  it('loads suggestion detail by route id', async () => {
    const { default: View } = await import('../SuggestionDetailView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { suggestion: SuggestionDetail | null }
    expect(mockGetSuggestion).toHaveBeenCalledWith(9)
    expect(vm.suggestion?.id).toBe(9)
    expect(wrapper.text()).toContain('建议单详情')
  })
})
