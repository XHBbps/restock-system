// @vitest-environment jsdom

import { readFileSync } from 'node:fs'

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
  template: '<div class="dashboard-chart-card-stub"><slot /><slot name="footer" /></div>',
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
  SkuCard: {
    props: ['sku', 'name'],
    template: '<div class="sku-card-stub">{{ sku }}|{{ name }}</div>',
  },
  ElTooltip: { template: '<div><slot /></div>' },
  ElTag: { template: '<span><slot /></span>' },
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
        country: 'US',
        sale_days: 10,
      },
      {
        commodity_sku: 'SKU-1',
        commodity_name: 'Alpha',
        main_image: null,
        country: 'CA',
        sale_days: 15,
      },
      {
        commodity_sku: 'SKU-2',
        commodity_name: 'Beta',
        main_image: null,
        country: 'JP',
        sale_days: 18,
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

    expect(wrapper.text()).toContain('紧急 SKU:2|全部启用 SKU 中低于提前期 20 天')
    expect(wrapper.text()).toContain('临近补货:3|全部启用 SKU 中未低于提前期，且低于目标天数')
    expect(wrapper.text()).toContain('安全 SKU:4|全部启用 SKU 中不少于 60 天')
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

  it('renders urgent sku rows by country-level sale days', async () => {
    mockGetDashboardOverview.mockResolvedValue(makeOverview())

    const { default: View } = await import('../WorkspaceView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const source = readFileSync('src/views/WorkspaceView.vue', 'utf-8')
    expect(source).toContain('<span class="urgent-col-country">国家</span>')
    expect(source).toContain('item.sale_days == null ? \'-\' : `${item.sale_days}天`')

    const urgentItems = wrapper.findAll('.urgent-item')
    expect(urgentItems).toHaveLength(3)
    expect(wrapper.text()).toContain('US - 美国')
    expect(wrapper.text()).toContain('CA - 加拿大')
    expect(wrapper.text()).toContain('JP - 日本')
    expect(wrapper.text()).toContain('10天')
    expect(wrapper.text()).toContain('15天')
    expect(wrapper.text()).toContain('18天')
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
      legend: { show: boolean }
      series: Array<{ data: Array<{ name: string; value: number }> }>
    }

    expect(option.legend.show).toBe(false)
    expect(option.series[0].data).toEqual([
      { name: 'US - 美国', value: 10, itemStyle: expect.any(Object) },
      { name: 'JP - 日本', value: 6, itemStyle: expect.any(Object) },
      { name: 'CA - 加拿大', value: 5, itemStyle: expect.any(Object) },
    ])

    const legendItems = wrapper.findAll('.country-distribution-legend__item')
    expect(legendItems).toHaveLength(3)
    expect(legendItems[0].text()).toContain('US - 美国')
    expect(legendItems[0].text()).toContain('10')
    expect(legendItems[1].text()).toContain('JP - 日本')
    expect(legendItems[1].text()).toContain('6')
  })

  it('makes the suggestion progress block clickable without a separate detail button', async () => {
    mockGetDashboardOverview.mockResolvedValue(makeOverview())

    const { default: View } = await import('../WorkspaceView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('查看详情')

    const suggestionProgress = wrapper.find('.suggestion-progress')
    expect(suggestionProgress.exists()).toBe(true)
    expect(suggestionProgress.attributes('role')).toBe('button')
    expect(suggestionProgress.attributes('tabindex')).toBe('0')

    await suggestionProgress.trigger('click')
    await suggestionProgress.trigger('keydown.enter')
    await suggestionProgress.trigger('keydown.space')

    expect(mockPush).toHaveBeenNthCalledWith(1, '/restock/current')
    expect(mockPush).toHaveBeenNthCalledWith(2, '/restock/current')
    expect(mockPush).toHaveBeenNthCalledWith(3, '/restock/current')
  })

  it('uses a stretch container for the urgent sku list instead of a fixed max height', async () => {
    mockGetDashboardOverview.mockResolvedValue(makeOverview())

    const { default: View } = await import('../WorkspaceView.vue')
    shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const source = readFileSync('src/views/WorkspaceView.vue', 'utf-8')
    expect(source).toContain('class="urgent-card-content"')
    expect(source).toContain('.urgent-card-content')
    expect(source).not.toContain('max-height: 400px')
  })

  it('uses a custom wrapping legend for country distribution instead of echarts built-in legend layout', async () => {
    mockGetDashboardOverview.mockResolvedValue(makeOverview())

    const { default: View } = await import('../WorkspaceView.vue')
    shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const source = readFileSync('src/views/WorkspaceView.vue', 'utf-8')
    expect(source).toContain('class="country-distribution-legend"')
    expect(source).toContain('.country-distribution-legend')
    expect(source).toContain("legend: { show: false }")
    expect(source).toContain('grid-template-columns: repeat(4, minmax(0, max-content))')
    expect(source).toContain('justify-content: center')
  })

  it('keeps footer-specific chart height rules out of regular chart cards so the risk chart can render', () => {
    const source = readFileSync('src/components/dashboard/DashboardChartCard.vue', 'utf-8')
    expect(source).toContain("['dashboard-chart-card__chart', { 'has-footer': !!$slots.footer }]")
    expect(source).toContain('.dashboard-chart-card__chart.has-footer')
  })
})
