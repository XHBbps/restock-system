// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/stores/auth'

const { mockListSkuMappingRules, mockListPhysicalItemGroups, messageWarning } = vi.hoisted(() => ({
  mockListSkuMappingRules: vi.fn(),
  mockListPhysicalItemGroups: vi.fn(),
  messageWarning: vi.fn()
}))

vi.mock('@/api/config', () => ({
  createPhysicalItemGroup: vi.fn(),
  createSkuMappingRule: vi.fn(),
  deletePhysicalItemGroup: vi.fn(),
  deleteSkuMappingRule: vi.fn(),
  exportSkuMappingRules: vi.fn(),
  importSkuMappingRules: vi.fn(),
  listPhysicalItemGroups: (...args: unknown[]) => mockListPhysicalItemGroups(...args),
  listSkuMappingRules: (...args: unknown[]) => mockListSkuMappingRules(...args),
  updatePhysicalItemGroup: vi.fn(),
  updateSkuMappingRule: vi.fn()
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: {
      success: vi.fn(),
      warning: messageWarning,
      error: vi.fn()
    },
    ElMessageBox: {
      confirm: vi.fn()
    }
  }
})

const STUBS = {
  PageSectionCard: {
    props: ['title', 'description'],
    template:
      '<section><h2>{{ title }}</h2><p v-if="description">{{ description }}</p><slot name="actions" /><slot /></section>'
  },
  TablePaginationBar: true,
  ElInput: true,
  ElSelect: true,
  ElOption: true,
  ElButton: { template: '<button type="button"><slot /></button>' },
  ElTable: true,
  ElTableColumn: true,
  ElTag: true,
  ElDialog: {
    props: ['title'],
    template: '<div><h3>{{ title }}</h3><slot /><slot name="footer" /></div>'
  },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { template: '<div><slot /></div>' },
  ElSwitch: true,
  ElInputNumber: true
}

describe('SkuMappingRuleView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockListSkuMappingRules.mockResolvedValue({ items: [], total: 0 })
    mockListPhysicalItemGroups.mockResolvedValue({ items: [], total: 0 })
    const auth = useAuthStore()
    auth.setAuth('test-token', {
      id: 1,
      username: 'tester',
      displayName: 'Tester',
      roleName: 'Admin',
      isSuperadmin: true,
      passwordIsDefault: false,
      permissions: ['config:edit']
    })
  })

  it('previews alternative groups with 或 separator', async () => {
    const { default: View } = await import('../SkuMappingRuleView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      form: {
        commodity_sku: string
        components: Array<{ group_no: number; inventory_sku: string; quantity: number }>
      }
      formulaPreview: string
    }

    vm.form.commodity_sku = 'A'
    vm.form.components = [
      { group_no: 1, inventory_sku: 'B', quantity: 1 },
      { group_no: 1, inventory_sku: 'C', quantity: 2 },
      { group_no: 2, inventory_sku: 'D', quantity: 1 }
    ]

    expect(vm.formulaPreview).toBe('A=1*B+2*C 或 1*D')
  })

  it('builds payload with group numbers', async () => {
    const { default: View } = await import('../SkuMappingRuleView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      form: {
        commodity_sku: string
        components: Array<{ group_no: number; inventory_sku: string; quantity: number }>
      }
      buildPayload: () => unknown
    }

    vm.form.commodity_sku = 'A'
    vm.form.components = [
      { group_no: 2, inventory_sku: 'D', quantity: 1 },
      { group_no: 1, inventory_sku: 'B', quantity: 1 }
    ]

    expect(vm.buildPayload()).toEqual(
      expect.objectContaining({
        commodity_sku: 'A',
        components: [
          { group_no: 1, inventory_sku: 'B', quantity: 1 },
          { group_no: 2, inventory_sku: 'D', quantity: 1 }
        ]
      })
    )
  })

  it('rejects non-positive group numbers before save', async () => {
    const { default: View } = await import('../SkuMappingRuleView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      form: {
        commodity_sku: string
        components: Array<{ group_no: number; inventory_sku: string; quantity: number }>
      }
      buildPayload: () => unknown
    }

    vm.form.commodity_sku = 'A'
    vm.form.components = [{ group_no: 0, inventory_sku: 'B', quantity: 1 }]

    expect(vm.buildPayload()).toBeNull()
    expect(messageWarning).toHaveBeenCalledWith('组合编号必须为正整数')
  })

  it('builds physical group payload with members only', async () => {
    const { default: View } = await import('../SkuMappingRuleView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      physicalForm: {
        name: string
        members: string[]
      }
      buildPhysicalPayload: () => unknown
    }

    vm.physicalForm.name = 'B/E'
    vm.physicalForm.members = [' B ', 'E']

    expect(vm.buildPhysicalPayload()).toEqual({
      name: 'B/E',
      enabled: true,
      remark: null,
      members: ['B', 'E']
    })
  })

  it('uses updated physical group copy and removes section descriptions', async () => {
    const { default: View } = await import('../SkuMappingRuleView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('库存共用组')
    expect(text).toContain('新增库存共用组')
    expect(text).toContain('添加SKU')
    expect(text).not.toContain('库存 SKU 共享组')
    expect(text).not.toContain('新增库存 SKU 共享组')
    expect(text).not.toContain('添加成员')
    expect(text).not.toContain('维护商品 SKU 与库存包裹 SKU 的组装关系')
    expect(text).not.toContain('维护完全等价的库存组件 SKU')
  })
})
