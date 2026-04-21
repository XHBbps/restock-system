// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { SuggestionDetail } from '@/api/suggestion'
import { useAuthStore } from '@/stores/auth'

const mockGetCurrentSuggestion = vi.fn()
const mockGetGenerationToggle = vi.fn()

vi.mock('@/api/suggestion', () => ({
  getCurrentSuggestion: (...args: unknown[]) => mockGetCurrentSuggestion(...args),
}))

vi.mock('@/api/config', () => ({
  getGenerationToggle: (...args: unknown[]) => mockGetGenerationToggle(...args),
}))

vi.mock('@/api/engine', () => ({
  runEngine: vi.fn(),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
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
    global_config_snapshot: {},
    created_at: '2026-04-13T10:00:00',
    archived_at: null,
    items: [],
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
}

describe('SuggestionListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockGetCurrentSuggestion.mockResolvedValue(makeSuggestion())
    mockGetGenerationToggle.mockResolvedValue({
      enabled: true,
      updated_by: 1,
      updated_by_name: 'Tester',
      updated_at: '2026-04-19T10:00:00+08:00',
      can_enable: true,
      can_enable_reason: null,
    })
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
    const { default: View } = await import('../SuggestionListView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { suggestion: SuggestionDetail | null }
    expect(mockGetCurrentSuggestion).toHaveBeenCalled()
    expect(mockGetGenerationToggle).toHaveBeenCalled()
    expect(vm.suggestion?.id).toBe(1)
  })

  it('disables generate button when toggle is null', async () => {
    mockGetGenerationToggle.mockRejectedValue(new Error('forbidden'))

    const { default: View } = await import('../SuggestionListView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const button = wrapper.findAll('button').find((item) => item.text().includes('生成采补建议'))
    expect(button?.attributes('disabled')).toBeDefined()
  })
})
