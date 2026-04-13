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
    props: ['title', 'value', 'hint'],
    template: '<div class="stat-card">{{ title }}:{{ value }}|{{ hint }}</div>',
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
    warning_count: 3,
    safe_count: 4,
    risk_country_count: 3,
    suggestion_id: 9,
    suggestion_status: 'draft',
    lead_time_days: 20,
    target_days: 60,
    country_risk_distribution: [
      { country: 'US', urgent_count: 1, warning_count: 2, safe_count: 3, total_count: 6 },
      { country: 'CA', urgent_count: 2, warning_count: 0, safe_count: 1, total_count: 3 },
    ],
    country_restock_distribution: [
      { country: 'US', total_qty: 10 },
      { country: 'JP', total_qty: 6 },
      { country: 'CA', total_qty: 5 },
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

  it('renders grouped country risk distribution chart and risk overview cards', async () => {
    mockGetDashboardOverview.mockResolvedValue(makeOverview())

    const { default: View } = await import('../WorkspaceView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    expect(wrapper.text()).toContain('紧急 SKU:2|低于提前期 20 天')
    expect(wrapper.text()).toContain('临近补货:3|未低于提前期，且低于目标天数')
    expect(wrapper.text()).toContain('安全 SKU:4|不少于 60 天')
    expect(wrapper.text()).toContain('覆盖国家:3|基于当前建议单快照')

    const chartCards = wrapper.findAllComponents(DashboardChartCardStub)
    expect(chartCards).toHaveLength(2)

    const leftChart = chartCards[0]
    expect(leftChart.props('title')).toBe('各国缺货风险分布')
    expect(leftChart.props('empty')).toBe(false)

    const option = leftChart.props('option') as {
      xAxis: { data: string[] }
      series: Array<{ name: string; stack?: string; data: number[] }>
    }

    expect(option.xAxis.data).toEqual(['US - 美国', 'CA - 加拿大'])
    expect(option.series).toHaveLength(3)
    expect(option.series.map((item) => item.name)).toEqual(['紧急', '临近补货', '安全'])
    expect(option.series.every((item) => item.stack == null)).toBe(true)
    expect(option.series[0].data).toEqual([1, 2])
    expect(option.series[1].data).toEqual([2, 0])
    expect(option.series[2].data).toEqual([3, 1])
  })

  it('renders country distribution chart from current suggestion breakdown', async () => {
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
      { name: 'US - 美国', value: 10, itemStyle: expect.any(Object) },
      { name: 'JP - 日本', value: 6, itemStyle: expect.any(Object) },
      { name: 'CA - 加拿大', value: 5, itemStyle: expect.any(Object) },
    ])
  })
})
