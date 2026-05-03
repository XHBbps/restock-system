// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { RecentCall } from '@/api/monitor'

const mockGetApiCallsOverview = vi.fn()
const mockGetRecentCalls = vi.fn()
const mockRetryCall = vi.fn()

vi.mock('@/api/monitor', () => ({
  getApiCallsOverview: (...args: unknown[]) => mockGetApiCallsOverview(...args),
  getRecentCalls: (...args: unknown[]) => mockGetRecentCalls(...args),
  retryCall: (...args: unknown[]) => mockRetryCall(...args),
}))

const STUBS = {
  DashboardPageHeader: {
    props: ['title'],
    template: '<div><h1>{{ title }}</h1><slot name="actions" /></div>',
  },
  DashboardStatCard: {
    props: ['title', 'value'],
    template: '<div>{{ title }}:{{ value }}</div>',
  },
  DashboardChartCard: {
    props: ['title'],
    template: '<section>{{ title }}</section>',
  },
  DataTableCard: {
    props: ['title'],
    template: '<section><h2>{{ title }}</h2><slot /><slot name="pagination" /></section>',
  },
  TablePaginationBar: {
    props: ['total'],
    template: '<div class="pagination-stub">{{ total }}</div>',
  },
  FailedApiCallTable: {
    props: ['rows'],
    template: `
      <div class="failed-api-call-table-stub">
        <div v-for="row in rows" :key="row.id">
          {{ row.retry_display_text }}|{{ row.retry_attempt_text }}
        </div>
      </div>
    `,
  },
  TaskProgress: true,
  ElSwitch: {
    props: ['modelValue'],
    emits: ['update:modelValue', 'change'],
    template: '<button type="button" @click="$emit(\'update:modelValue\', !modelValue); $emit(\'change\', !modelValue)">switch</button>',
  },
  ElButton: {
    template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
  },
  ElTable: true,
  ElTableColumn: true,
}

function makeRecentCall(overrides: Partial<RecentCall> = {}): RecentCall {
  return {
    id: 1,
    endpoint: '/api/shop/pageList.json',
    called_at: '2026-05-03T12:00:00+08:00',
    duration_ms: 88,
    http_status: 200,
    saihu_code: 40019,
    saihu_msg: 'rate limited',
    error_type: 'rate_limit',
    retry_status: null,
    retry_display_status: 'not_queued',
    retry_display_text: '未入自动队列',
    retry_attempt_text: '-',
    auto_retry_attempts: 0,
    next_retry_at: null,
    resolved_at: null,
    last_retry_error: null,
    retry_source_log_id: null,
    has_request_payload: true,
    can_retry: true,
    ...overrides,
  }
}

describe('ApiMonitorView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetApiCallsOverview.mockResolvedValue({ endpoints: [] })
    mockGetRecentCalls.mockResolvedValue([makeRecentCall()])
  })

  it('renders retry display fields from recent calls without fallback 0/5', async () => {
    const { default: View } = await import('../ApiMonitorView.vue')
    const wrapper = shallowMount(View, {
      global: {
        stubs: STUBS,
        directives: { loading: {} },
      },
    })
    await flushPromises()

    expect(mockGetRecentCalls).toHaveBeenCalledWith({ only_failed: true, limit: 200 })
    expect(wrapper.text()).toContain('未入自动队列|-')
    expect(wrapper.text()).not.toContain('0/5')
  })
})
