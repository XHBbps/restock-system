// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { GlobalConfig } from '@/api/config'

const mockGetGlobalConfig = vi.fn()
const mockPatchGlobalConfig = vi.fn()
const messageSuccess = vi.fn()
const messageWarning = vi.fn()
const messageError = vi.fn()

vi.mock('@/api/config', () => ({
  getGlobalConfig: (...args: unknown[]) => mockGetGlobalConfig(...args),
  patchGlobalConfig: (...args: unknown[]) => mockPatchGlobalConfig(...args),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: {
      success: messageSuccess,
      warning: messageWarning,
      error: messageError,
    },
  }
})

const STUBS = {
  PageSectionCard: {
    props: ['title'],
    template: '<div><h1>{{ title }}</h1><slot name="actions" /><slot /></div>',
  },
  ElButton: true,
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { template: '<div><slot /></div>' },
  ElInputNumber: true,
  ElInput: true,
  ElSwitch: true,
  ElSelect: true,
  ElOption: true,
  ElRadioGroup: true,
  ElRadioButton: true,
}

function makeConfig(overrides: Partial<GlobalConfig> = {}): GlobalConfig {
  return {
    buffer_days: 30,
    target_days: 60,
    lead_time_days: 50,
    restock_regions: [],
    sync_interval_minutes: 60,
    calc_cron: '0 8 * * *',
    calc_enabled: true,
    default_purchase_warehouse_id: 'WH-001',
    include_tax: '0',
    shop_sync_mode: 'all',
    ...overrides,
  }
}

describe('GlobalConfigView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads global config on mount and keeps restock regions in form state', async () => {
    mockGetGlobalConfig.mockResolvedValue(makeConfig({ restock_regions: ['US', 'GB'] }))

    const { default: View } = await import('../GlobalConfigView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { form: GlobalConfig | null }
    expect(mockGetGlobalConfig).toHaveBeenCalledTimes(1)
    expect(vm.form?.restock_regions).toEqual(['US', 'GB'])
  })

  it('submits restock regions when saving', async () => {
    mockGetGlobalConfig.mockResolvedValue(makeConfig())
    mockPatchGlobalConfig.mockResolvedValue(makeConfig({ restock_regions: ['US', 'GB'] }))

    const { default: View } = await import('../GlobalConfigView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { form: GlobalConfig | null; save: () => Promise<void> }
    if (!vm.form) throw new Error('expected form to be initialized')

    vm.form.restock_regions = ['US', 'GB']
    await vm.save()

    expect(mockPatchGlobalConfig).toHaveBeenCalledWith(
      expect.objectContaining({
        restock_regions: ['US', 'GB'],
      }),
    )
    expect(messageSuccess).toHaveBeenCalled()
  })

  it('shows recalculation warning when restock regions change', async () => {
    mockGetGlobalConfig.mockResolvedValue(makeConfig({ restock_regions: ['US'] }))
    mockPatchGlobalConfig.mockResolvedValue(makeConfig({ restock_regions: ['US', 'GB'] }))

    const { default: View } = await import('../GlobalConfigView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { form: GlobalConfig | null; save: () => Promise<void> }
    if (!vm.form) throw new Error('expected form to be initialized')

    vm.form.restock_regions = ['US', 'GB']
    await vm.save()

    expect(messageWarning).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.stringContaining('补货区域'),
      }),
    )
  })

  it('blocks saving when target days is smaller than lead time', async () => {
    mockGetGlobalConfig.mockResolvedValue(makeConfig({ target_days: 30, lead_time_days: 20 }))

    const { default: View } = await import('../GlobalConfigView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { form: GlobalConfig | null; save: () => Promise<void> }
    if (!vm.form) throw new Error('expected form to be initialized')

    vm.form.target_days = 15
    vm.form.lead_time_days = 20
    await vm.save()

    expect(mockPatchGlobalConfig).not.toHaveBeenCalled()
    expect(messageError).toHaveBeenCalledWith('目标库存天数不能小于采购提前期')
  })
})
