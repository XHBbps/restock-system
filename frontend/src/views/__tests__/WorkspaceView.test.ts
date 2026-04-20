// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { DashboardOverview } from '@/api/dashboard'
import { useAuthStore } from '@/stores/auth'
import { getCountryLabel } from '@/utils/countries'

const mockGetDashboardOverview = vi.fn()
const mockRefreshDashboardSnapshot = vi.fn()
const mockPush = vi.fn()
const mockMessageSuccess = vi.fn()
const mockMessageError = vi.fn()
const mockMessageWarning = vi.fn()

vi.mock('@/api/dashboard', () => ({
  getDashboardOverview: (...args: unknown[]) => mockGetDashboardOverview(...args),
  refreshDashboardSnapshot: (...args: unknown[]) => mockRefreshDashboardSnapshot(...args),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  return {
    ...actual,
    ElMessage: {
      success: (...args: unknown[]) => mockMessageSuccess(...args),
      error: (...args: unknown[]) => mockMessageError(...args),
      warning: (...args: unknown[]) => mockMessageWarning(...args),
    },
  }
})

const DashboardChartCardStub = {
  name: 'DashboardChartCard',
  props: ['title', 'option', 'empty', 'emptyText'],
  template: '<div class="dashboard-chart-card-stub"><slot /><slot name="footer" /></div>',
}

const STUBS = {
  DashboardPageHeader: {
    props: ['title'],
    template: `
      <div class="page-header">
        <div class="page-header__title">{{ title }}</div>
        <div class="page-header__meta"><slot name="meta" /></div>
        <div class="page-header__actions"><slot name="actions" /></div>
      </div>
    `,
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
  SkuCard: {
    props: ['sku', 'name'],
    template: '<div class="sku-card-stub">{{ sku }}|{{ name }}</div>',
  },
  TaskProgress: {
    props: ['taskId'],
    template: '<div class="task-progress-stub">task:{{ taskId }}</div>',
  },
  ElTooltip: { template: '<div><slot /></div>' },
  ElTag: { template: '<span><slot /></span>' },
  ElProgress: true,
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  ElEmpty: { props: ['description'], template: '<div class="empty">{{ description }}</div>' },
}

function makeOverview(overrides: Partial<DashboardOverview> = {}): DashboardOverview {
  return {
    enabled_sku_count: 12,
    restock_sku_count: 7,
    no_restock_sku_count: 5,
    suggestion_item_count: 8,
    exported_count: 3,
    urgent_count: 2,
    warning_count: 3,
    safe_count: 4,
    risk_country_count: 3,
    suggestion_id: 9,
    suggestion_status: 'draft',
    suggestion_snapshot_count: 1,
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
        sale_days: 0.4,
      },
      {
        commodity_sku: 'SKU-2',
        commodity_name: 'Beta',
        main_image: null,
        country: 'JP',
        sale_days: 18,
      },
    ],
    snapshot_status: 'ready',
    snapshot_updated_at: '2026-04-14T11:30:00+08:00',
    snapshot_task_id: null,
    ...overrides,
  }
}

describe('WorkspaceView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    const auth = useAuthStore()
    auth.setAuth('test-token', {
      id: 1,
      username: 'tester',
      displayName: 'Tester',
      roleName: 'Reader',
      isSuperadmin: false,
      passwordIsDefault: false,
      permissions: ['home:refresh'],
    })
  })

  it('renders country-level risk and restock charts from dashboard payload', async () => {
    mockGetDashboardOverview.mockResolvedValue(makeOverview())

    const { default: View } = await import('../WorkspaceView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    expect(wrapper.text()).toContain('7')
    expect(wrapper.text()).toContain('5')
    expect(wrapper.text()).toContain('3')

    const chartCards = wrapper.findAllComponents(DashboardChartCardStub)
    expect(chartCards).toHaveLength(2)

    const riskOption = chartCards[0].props('option') as {
      xAxis: { data: string[] }
      series: Array<{ data: number[] }>
    }
    expect(riskOption.xAxis.data).toEqual([getCountryLabel('US'), getCountryLabel('CA')])
    expect(riskOption.series[0].data).toEqual([1, 2])

    const restockOption = chartCards[1].props('option') as {
      series: Array<{ data: Array<{ name: string; value: number }> }>
    }
    expect(restockOption.series[0].data).toEqual([
      { name: getCountryLabel('US'), value: 10, itemStyle: expect.any(Object) },
      { name: getCountryLabel('JP'), value: 6, itemStyle: expect.any(Object) },
      { name: getCountryLabel('CA'), value: 5, itemStyle: expect.any(Object) },
    ])
  })

  it('renders urgent rows by country-level sale days', async () => {
    mockGetDashboardOverview.mockResolvedValue(makeOverview())

    const { default: View } = await import('../WorkspaceView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const urgentItems = wrapper.findAll('.urgent-item')
    expect(urgentItems).toHaveLength(3)
    expect(wrapper.text()).toContain(getCountryLabel('US'))
    expect(wrapper.text()).toContain(getCountryLabel('CA'))
    expect(wrapper.text()).toContain(getCountryLabel('JP'))
  })

  it('makes the suggestion progress block clickable', async () => {
    mockGetDashboardOverview.mockResolvedValue(makeOverview())

    const { default: View } = await import('../WorkspaceView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const suggestionProgress = wrapper.find('.suggestion-progress')
    expect(suggestionProgress.exists()).toBe(true)

    await suggestionProgress.trigger('click')
    await suggestionProgress.trigger('keydown.enter')
    await suggestionProgress.trigger('keydown.space')

    expect(mockPush).toHaveBeenNthCalledWith(1, '/restock/current')
    expect(mockPush).toHaveBeenNthCalledWith(2, '/restock/current')
    expect(mockPush).toHaveBeenNthCalledWith(3, '/restock/current')
  })

  it('shows task progress when snapshot is refreshing and supports manual refresh', async () => {
    mockGetDashboardOverview.mockResolvedValue(
      makeOverview({
        snapshot_status: 'refreshing',
        snapshot_task_id: 88,
      }),
    )
    mockRefreshDashboardSnapshot.mockResolvedValue({ task_id: 99, existing: false })

    const { default: View } = await import('../WorkspaceView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    expect(wrapper.find('.task-progress-stub').text()).toContain('task:88')

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(mockRefreshDashboardSnapshot).toHaveBeenCalled()
    expect(mockMessageSuccess).toHaveBeenCalled()
  })

  it('hides snapshot task polling for users without refresh permission', async () => {
    const auth = useAuthStore()
    auth.setAuth('test-token', {
      id: 1,
      username: 'viewer',
      displayName: 'Viewer',
      roleName: 'Viewer',
      isSuperadmin: false,
      passwordIsDefault: false,
      permissions: [],
    })
    mockGetDashboardOverview.mockResolvedValue(
      makeOverview({
        snapshot_status: 'missing',
        snapshot_task_id: 88,
        snapshot_updated_at: null,
      }),
    )

    const { default: View } = await import('../WorkspaceView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    expect(wrapper.find('.task-progress-stub').exists()).toBe(false)
  })
})
