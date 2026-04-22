// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { GlobalConfig } from '@/api/config'
import { useAuthStore } from '@/stores/auth'

const {
  mockGetGlobalConfig,
  mockPatchGlobalConfig,
  mockGetGenerationToggle,
  mockPatchGenerationToggle,
  messageSuccess,
  messageWarning,
  messageError,
  mockConfirm,
} = vi.hoisted(() => ({
  mockGetGlobalConfig: vi.fn(),
  mockPatchGlobalConfig: vi.fn(),
  mockGetGenerationToggle: vi.fn(),
  mockPatchGenerationToggle: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
  messageError: vi.fn(),
  mockConfirm: vi.fn(),
}))

vi.mock('@/api/config', () => ({
  getGlobalConfig: (...args: unknown[]) => mockGetGlobalConfig(...args),
  patchGlobalConfig: (...args: unknown[]) => mockPatchGlobalConfig(...args),
  getGenerationToggle: (...args: unknown[]) => mockGetGenerationToggle(...args),
  patchGenerationToggle: (...args: unknown[]) => mockPatchGenerationToggle(...args),
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
    ElMessageBox: {
      confirm: (...args: unknown[]) => mockConfirm(...args),
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
  ElSwitch: true,
  ElSelect: true,
  ElOption: true,
  ElRadioGroup: true,
  ElRadioButton: true,
  ElTooltip: { template: '<div><slot /></div>' },
  ElTag: { template: '<span><slot /></span>' },
}

function makeConfig(overrides: Partial<GlobalConfig> = {}): GlobalConfig {
  return {
    buffer_days: 30,
    target_days: 60,
    lead_time_days: 50,
    safety_stock_days: 15,
    restock_regions: [],
    eu_countries: ['DE', 'FR'],
    sync_interval_minutes: 60,
    scheduler_enabled: true,
    shop_sync_mode: 'all',
    ...overrides,
  }
}

describe('GlobalConfigView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
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
      roleName: 'Admin',
      isSuperadmin: true,
      passwordIsDefault: false,
      permissions: ['config:edit', 'restock:new_cycle'],
    })
  })

  it('loads global config and generation toggle on mount', async () => {
    mockGetGlobalConfig.mockResolvedValue(makeConfig({ restock_regions: ['US', 'EU'] }))

    const { default: View } = await import('../GlobalConfigView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { form: GlobalConfig | null }
    expect(mockGetGlobalConfig).toHaveBeenCalledTimes(1)
    expect(mockGetGenerationToggle).toHaveBeenCalledTimes(1)
    expect(vm.form?.restock_regions).toEqual(['US', 'EU'])
    expect(vm.form?.safety_stock_days).toBe(15)
  })

  it('submits safety stock and EU countries when saving', async () => {
    mockGetGlobalConfig.mockResolvedValue(makeConfig())
    mockPatchGlobalConfig.mockResolvedValue(makeConfig({ safety_stock_days: 30, eu_countries: ['DE'] }))

    const { default: View } = await import('../GlobalConfigView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { form: GlobalConfig | null; save: () => Promise<void> }
    if (!vm.form) throw new Error('expected form to be initialized')

    vm.form.safety_stock_days = 30
    vm.form.eu_countries = ['DE']
    await vm.save()

    expect(mockPatchGlobalConfig).toHaveBeenCalledWith(
      expect.objectContaining({
        safety_stock_days: 30,
        eu_countries: ['DE'],
      }),
    )
    expect(messageSuccess).toHaveBeenCalled()
  })

  it('blocks toggle-on when can_enable is false', async () => {
    mockGetGlobalConfig.mockResolvedValue(makeConfig())
    mockGetGenerationToggle.mockResolvedValue({
      enabled: false,
      updated_by: null,
      updated_by_name: null,
      updated_at: null,
      can_enable: false,
      can_enable_reason: '采购建议尚未导出任何快照',
    })

    const { default: View } = await import('../GlobalConfigView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { onToggleChange: (value: boolean) => Promise<void> }
    await vm.onToggleChange(true)

    expect(messageWarning).toHaveBeenCalledWith('采购建议尚未导出任何快照')
    expect(mockPatchGenerationToggle).not.toHaveBeenCalled()
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
    expect(messageError).toHaveBeenCalled()
  })
})
