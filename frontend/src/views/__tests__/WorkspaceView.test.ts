// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { DashboardOverview } from '@/api/dashboard'

const mockGetDashboardOverview = vi.fn()
const mockPush = vi.fn()

vi.mock('@/api/dashboard', () => ({
  getDashboardOverview: (...args: unknown[]) => mockGetDashboardOverview(...args),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
}))

const DashboardChartCardStub = {
  name: 'DashboardChartCard',
  props: ['title', 'option', 'empty', 'emptyText'],
  template: '<div class="dashboard-chart-card-stub"><slot /></div>',
}

const STUBS = {
  DashboardPageHeader: {
    props: ['title'],
    template: '<div class="page-header">{{ title }}</div>',
  },
  DashboardStatCard: {
    props: ['title', 'value'],
    template: '<div class="stat-card">{{ title }}:{{ value }}</div>',
  },
  DataTableCard: {
    props: ['title'],
    template: '<section><h2>{{ title }}</h2><slot /></section>',
  },
  DashboardChartCard: DashboardChartCardStub,
  SkuCard: true,
  ElTooltip: { template: '<div><slot /></div>' },
  ElTag: { template: '<span><slot /></span>' },
  ElButton: { template: '<button><slot /></button>' },
  ElProgress: true,
  ElEmpty: { props: ['description'], template: '<div class="empty">{{ description }}</div>' },
}

function makeOverview(overrides: Partial<DashboardOverview> = {}): DashboardOverview {
  return {
    enabled_sku_count: 12,
    suggestion_item_count: 8,
    pushed_count: 3,
    urgent_count: 2,
    suggestion_id: 9,
    suggestion_status: 'draft',
    lead_time_days: 20,
    target_days: 60,
    country_risk_distribution: [
      { country: 'US', urgent_count: 1, warning_count: 2, safe_count: 3, total_count: 6 },
      { country: 'CA', urgent_count: 2, warning_count: 0, safe_count: 1, total_count: 3 },
    ],
    top_urgent_skus: [
      {
        commodity_sku: 'SKU-1',
        commodity_name: 'Alpha',
        main_image: null,
        total_qty: 12,
        min_sale_days: 10,
        country_breakdown: { US: 7, CA: 5 },
      },
      {
        commodity_sku: 'SKU-2',
        commodity_name: 'Beta',
        main_image: null,
        total_qty: 9,
        min_sale_days: 18,
        country_breakdown: { US: 3, JP: 6 },
      },
    ],
    ...overrides,
  }
}

describe('WorkspaceView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders stacked country risk distribution chart from dashboard overview', async () => {
    mockGetDashboardOverview.mockResolvedValue(makeOverview())

    const { default: View } = await import('../WorkspaceView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const chartCards = wrapper.findAllComponents(DashboardChartCardStub)
    expect(chartCards).toHaveLength(2)

    const leftChart = chartCards[0]
    expect(leftChart.props('title')).toBe('各国缺货风险分布')
    expect(leftChart.props('empty')).toBe(false)

    const option = leftChart.props('option') as {
      xAxis: { data: string[] }
      series: Array<{ name: string; stack: string; data: number[] }>
    }

    expect(option.xAxis.data).toEqual(['US - 美国', 'CA - 加拿大'])
    expect(option.series).toHaveLength(3)
    expect(option.series.map((item) => item.name)).toEqual(['紧急', '临近补货', '安全'])
    expect(option.series.map((item) => item.stack)).toEqual(['risk', 'risk', 'risk'])
    expect(option.series[0].data).toEqual([1, 2])
    expect(option.series[1].data).toEqual([2, 0])
    expect(option.series[2].data).toEqual([3, 1])
  })

  it('keeps the right-side replenishment country distribution chart', async () => {
    mockGetDashboardOverview.mockResolvedValue(makeOverview())

    const { default: View } = await import('../WorkspaceView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const chartCards = wrapper.findAllComponents(DashboardChartCardStub)
    const rightChart = chartCards[1]

    expect(rightChart.props('title')).toBe('补货量国家分布')

    const option = rightChart.props('option') as {
      series: Array<{ data: Array<{ name: string; value: number }> }>
    }

    expect(option.series[0].data).toEqual([
      { name: 'US', value: 10, itemStyle: expect.any(Object) },
      { name: 'JP', value: 6, itemStyle: expect.any(Object) },
      { name: 'CA', value: 5, itemStyle: expect.any(Object) },
    ])
  })
})
