// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { GlobalConfig } from '@/api/config'
import { useAuthStore } from '@/stores/auth'

const {
  mockGetGlobalConfig,
  mockGetCountryOptions,
  mockPatchGlobalConfig,
  mockGetGenerationToggle,
  mockPatchGenerationToggle,
  messageSuccess,
  messageWarning,
  messageError,
  mockConfirm,
} = vi.hoisted(() => ({
  mockGetGlobalConfig: vi.fn(),
  mockGetCountryOptions: vi.fn(),
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
  getCountryOptions: (...args: unknown[]) => mockGetCountryOptions(...args),
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
  ElAlert: true,
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
    order_sync_interval_minutes: 120,
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
    mockGetCountryOptions.mockResolvedValue({
      items: [
        { code: 'EU', label: 'EU - 欧盟', builtin: true, observed: true, can_be_eu_member: false },
        { code: 'ZZ', label: 'ZZ - 无法识别国家', builtin: true, observed: false, can_be_eu_member: false },
        { code: 'US', label: 'US - 美国', builtin: true, observed: true, can_be_eu_member: true },
        { code: 'GB', label: 'GB - 英国', builtin: true, observed: true, can_be_eu_member: true },
        { code: 'CZ', label: 'CZ - 捷克', builtin: true, observed: true, can_be_eu_member: true },
        { code: 'DE', label: 'DE - 德国', builtin: true, observed: true, can_be_eu_member: true },
        { code: 'RO', label: 'RO - 罗马尼亚', builtin: true, observed: true, can_be_eu_member: true },
      ],
      unknown_country_codes: [],
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
    expect(mockGetCountryOptions).toHaveBeenCalledTimes(1)
    expect(mockGetGenerationToggle).toHaveBeenCalledTimes(1)
    expect(vm.form?.restock_regions).toEqual(['US', 'EU'])
    expect(vm.form?.safety_stock_days).toBe(15)
  })

  it('uses backend country option labels for member country selects', async () => {
    mockGetGlobalConfig.mockResolvedValue(makeConfig())

    const { default: View } = await import('../GlobalConfigView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      countryOptions: Array<{ code: string; label: string }>
      euCountryOptions: Array<{ code: string; label: string }>
    }
    expect(vm.countryOptions.map((option) => option.label)).toContain('GB - 英国')
    expect(vm.countryOptions.map((option) => option.label)).toContain('CZ - 捷克')
    expect(vm.countryOptions.map((option) => option.label)).toContain('RO - 罗马尼亚')
    expect(vm.euCountryOptions.map((option) => option.code)).not.toContain('EU')
    expect(vm.euCountryOptions.map((option) => option.code)).not.toContain('ZZ')
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

  it('submits regular and order sync intervals when saving', async () => {
    mockGetGlobalConfig.mockResolvedValue(makeConfig())
    mockPatchGlobalConfig.mockResolvedValue(
      makeConfig({ sync_interval_minutes: 45, order_sync_interval_minutes: 120 }),
    )

    const { default: View } = await import('../GlobalConfigView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { form: GlobalConfig | null; save: () => Promise<void> }
    if (!vm.form) throw new Error('expected form to be initialized')

    vm.form.sync_interval_minutes = 45
    vm.form.order_sync_interval_minutes = 120
    await vm.save()

    expect(mockPatchGlobalConfig).toHaveBeenCalledWith(
      expect.objectContaining({
        sync_interval_minutes: 45,
        order_sync_interval_minutes: 120,
      }),
    )
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
