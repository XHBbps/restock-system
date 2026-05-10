// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { isSubCategory, navigationGroups } from '@/config/navigation'
import { useAuthStore } from '@/stores/auth'
import { useSidebarStore } from '@/stores/sidebar'

const mockReplace = vi.fn()
const mockLogout = vi.fn()
const mockChangeOwnPassword = vi.fn()

vi.mock('vue-router', () => ({
  RouterLink: {
    props: ['to'],
    emits: ['click'],
    template: '<a class="router-link-stub" :data-to="to" @click="$emit(\'click\')"><slot /></a>',
  },
  RouterView: { template: '<div class="router-view-stub" />' },
  useRoute: () => ({
    path: '/workspace',
    meta: { title: '信息总览', section: 'HOME' },
  }),
  useRouter: () => ({ replace: mockReplace }),
}))

vi.mock('@/api/auth', () => ({
  changeOwnPassword: (...args: unknown[]) => mockChangeOwnPassword(...args),
  logout: (...args: unknown[]) => mockLogout(...args),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  return {
    ...actual,
    ElMessage: {
      warning: vi.fn(),
      success: vi.fn(),
      error: vi.fn(),
    },
  }
})

const STUBS = {
  RouterLink: {
    props: ['to'],
    emits: ['click'],
    template: '<a class="router-link-stub" :data-to="to" @click="$emit(\'click\')"><slot /></a>',
  },
  RouterView: { template: '<div class="router-view-stub" />' },
  ElDrawer: {
    props: ['modelValue'],
    template: '<div v-if="modelValue" class="drawer"><slot /></div>',
  },
  ElDialog: { template: '<div><slot /><slot name="footer" /></div>' },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { template: '<label><slot /></label>' },
  ElInput: true,
  ElButton: { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  Teleport: true,
}

describe('AppLayout', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()

    const auth = useAuthStore()
    auth.setAuth('test-token', {
      id: 1,
      username: 'tester',
      displayName: 'Tester',
      roleName: 'Admin',
      isSuperadmin: false,
      passwordIsDefault: false,
      permissions: [
        'home:view',
        'restock:view',
        'history:view',
        'data_base:view',
        'data_biz:view',
        'sync:view',
        'config:view',
        'monitor:view',
        'auth:view',
      ],
    })
  })

  it('opens mobile navigation and can close it from the orders link', async () => {
    const { default: AppLayout } = await import('../AppLayout.vue')
    const sidebar = useSidebarStore()
    for (const group of navigationGroups) {
      for (const child of group.children) {
        if (isSubCategory(child)) sidebar.ensureCategoryExpanded(child.label)
      }
    }

    const wrapper = mount(AppLayout, { global: { stubs: STUBS } })

    expect(wrapper.find('.mobile-nav-shell').exists()).toBe(false)

    await wrapper.find('.mobile-menu-btn').trigger('click')
    expect(wrapper.find('.mobile-nav-shell').exists()).toBe(true)

    await wrapper.vm.$nextTick()

    const ordersLink = wrapper.find('[data-to="/data/orders"]')
    expect(ordersLink.exists()).toBe(true)

    await ordersLink.trigger('click')
    expect(wrapper.find('.mobile-nav-shell').exists()).toBe(false)
  })
})
