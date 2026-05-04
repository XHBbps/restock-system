// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import dayjs from 'dayjs'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { SchedulerStatus } from '@/api/sync'
import { useAuthStore } from '@/stores/auth'

const mockListSyncState = vi.fn()
const mockGetSchedulerStatus = vi.fn()
const mockSetSchedulerStatus = vi.fn()
const mockClientPost = vi.fn()
const mockMessageSuccess = vi.fn()
const mockMessageError = vi.fn()
const mockMessageWarning = vi.fn()

vi.mock('@/api/data', () => ({
  listSyncState: (...args: unknown[]) => mockListSyncState(...args)
}))

vi.mock('@/api/sync', () => ({
  getSchedulerStatus: (...args: unknown[]) => mockGetSchedulerStatus(...args),
  setSchedulerStatus: (...args: unknown[]) => mockSetSchedulerStatus(...args)
}))

vi.mock('@/api/client', () => ({
  default: {
    post: (...args: unknown[]) => mockClientPost(...args)
  }
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  return {
    ...actual,
    ElMessage: {
      success: (...args: unknown[]) => mockMessageSuccess(...args),
      error: (...args: unknown[]) => mockMessageError(...args),
      warning: (...args: unknown[]) => mockMessageWarning(...args)
    }
  }
})

const DashboardChartCardStub = {
  name: 'DashboardChartCard',
  props: ['title', 'description', 'option', 'empty', 'emptyText'],
  template:
    '<div class="dashboard-chart-card-stub">{{ title }}{{ description }}{{ emptyText }}</div>'
}

const STUBS = {
  DashboardPageHeader: {
    props: ['title'],
    template: '<header><slot name="meta" /><slot name="actions" /></header>'
  },
  DashboardStatCard: {
    props: ['title', 'value', 'hint'],
    template: '<div class="stat-card-stub">{{ title }}{{ value }}{{ hint }}</div>'
  },
  DashboardChartCard: DashboardChartCardStub,
  DataTableCard: {
    props: ['title'],
    template: '<section><slot name="toolbar" /><slot /></section>'
  },
  SchedulerControlPanel: true,
  DashboardSection: {
    props: ['title'],
    template: '<section><slot /></section>'
  },
  SyncTaskCard: {
    props: ['title'],
    template: '<article>{{ title }}<slot name="actions" /></article>'
  },
  SyncTaskHeroCard: true,
  TaskProgress: true,
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  ElTag: { template: '<span><slot /></span>' }
}

function makeSchedulerStatus(overrides: Partial<SchedulerStatus> = {}): SchedulerStatus {
  return {
    enabled: true,
    running: true,
    timezone: 'Asia/Shanghai',
    sync_interval_minutes: 60,
    order_sync_interval_minutes: 120,
    calc_cron: '0 8 * * *',
    jobs: [
      { job_name: 'sync_inventory', next_run_time: '2026-04-30T10:45:00+08:00' },
      { job_name: 'sync_order_list', next_run_time: '2026-04-30T10:30:00+08:00' },
      { job_name: 'sync_warehouse', next_run_time: '2026-04-30T13:00:00+08:00' }
    ],
    ...overrides
  }
}

async function mountView(status: SchedulerStatus) {
  mockGetSchedulerStatus.mockResolvedValue(status)
  mockListSyncState.mockResolvedValue([])

  const { default: View } = await import('../SyncConsoleView.vue')
  const wrapper = shallowMount(View, { global: { stubs: STUBS } })
  await flushPromises()
  return wrapper
}

describe('SyncConsoleView', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-04-30T10:00:00+08:00'))
    setActivePinia(createPinia())
    vi.clearAllMocks()

    const auth = useAuthStore()
    auth.setAuth('test-token', {
      id: 1,
      username: 'tester',
      displayName: 'Tester',
      roleName: 'Operator',
      isSuperadmin: false,
      passwordIsDefault: false,
      permissions: ['sync:operate']
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders the next run chart as a time-based scatter timeline', async () => {
    const wrapper = await mountView(makeSchedulerStatus())

    const chart = wrapper.findComponent(DashboardChartCardStub)
    expect(chart.props('description')).toBe('按计划时间查看自动任务的下一次触发点')

    const option = chart.props('option') as {
      xAxis: { type: string; min: number; max: number }
      yAxis: { type: string; data: string[] }
      series: Array<{
        type: string
        data: Array<{ name: string; value: [number, string]; itemStyle: { color: string } }>
      }>
    }

    expect(option.xAxis.type).toBe('time')
    expect(option.yAxis.type).toBe('category')
    expect(option.series[0].type).toBe('scatter')
    expect(option.yAxis.data).toEqual(['订单处理列表同步', '库存同步', '仓库基础同步'])
    expect(option.series[0].data.map((item) => item.value[1])).toEqual([
      '订单处理列表同步',
      '库存同步',
      '仓库基础同步'
    ])
    expect(option.series[0].data[0].itemStyle.color).toBe('#2563eb')
    expect(option.series[0].data[2].itemStyle.color).toBe('#71717a')
    expect(option.xAxis.min).toBe(new Date('2026-04-30T10:00:00+08:00').getTime())
    expect(option.xAxis.max).toBe(new Date('2026-04-30T13:15:00+08:00').getTime())
  })

  it('formats tooltip with job name, next run time, and remaining time', async () => {
    const wrapper = await mountView(makeSchedulerStatus())
    const option = wrapper.findComponent(DashboardChartCardStub).props('option') as {
      tooltip: { formatter: (params: unknown) => string }
      series: Array<{ data: unknown[] }>
    }

    const html = option.tooltip.formatter({ data: option.series[0].data[0] })

    expect(html).toContain('任务：订单处理列表同步')
    expect(html).toContain(
      `下次执行：${dayjs('2026-04-30T10:30:00+08:00').format('MM-DD HH:mm:ss')}`
    )
    expect(html).toContain('距离执行：30 分钟')
  })

  it('uses the scheduler disabled empty text when no jobs are scheduled', async () => {
    const wrapper = await mountView(makeSchedulerStatus({ enabled: false }))
    const chart = wrapper.findComponent(DashboardChartCardStub)

    expect(chart.props('empty')).toBe(true)
    expect(chart.props('emptyText')).toBe('自动调度已关闭')
  })

  it('uses the fallback empty text when scheduler is enabled but has no jobs', async () => {
    const wrapper = await mountView(makeSchedulerStatus({ enabled: true, jobs: [] }))
    const chart = wrapper.findComponent(DashboardChartCardStub)

    expect(chart.props('empty')).toBe(true)
    expect(chart.props('emptyText')).toBe('暂无下次执行计划')
  })
})
