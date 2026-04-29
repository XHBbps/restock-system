// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { PermissionOut, RoleOut } from '@/api/auth-management'
import { useAuthStore } from '@/stores/auth'

const {
  mockGetRoles,
  mockGetPermissions,
  mockGetRolePermissions,
  mockCreateRole,
  mockUpdateRole,
  mockUpdateRolePermissions,
  mockDeleteRole,
  mockConfirm,
  mockRouterReplace,
  messageSuccess,
  messageError,
  messageWarning,
} = vi.hoisted(() => ({
  mockGetRoles: vi.fn(),
  mockGetPermissions: vi.fn(),
  mockGetRolePermissions: vi.fn(),
  mockCreateRole: vi.fn(),
  mockUpdateRole: vi.fn(),
  mockUpdateRolePermissions: vi.fn(),
  mockDeleteRole: vi.fn(),
  mockConfirm: vi.fn(),
  mockRouterReplace: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
  messageWarning: vi.fn(),
}))

vi.mock('@/api/auth-management', () => ({
  getRoles: (...args: unknown[]) => mockGetRoles(...args),
  getPermissions: (...args: unknown[]) => mockGetPermissions(...args),
  getRolePermissions: (...args: unknown[]) => mockGetRolePermissions(...args),
  createRole: (...args: unknown[]) => mockCreateRole(...args),
  updateRole: (...args: unknown[]) => mockUpdateRole(...args),
  updateRolePermissions: (...args: unknown[]) => mockUpdateRolePermissions(...args),
  deleteRole: (...args: unknown[]) => mockDeleteRole(...args),
}))

vi.mock('@/router', () => ({
  default: {
    replace: (...args: unknown[]) => mockRouterReplace(...args),
  },
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: {
      success: (...args: unknown[]) => messageSuccess(...args),
      error: (...args: unknown[]) => messageError(...args),
      warning: (...args: unknown[]) => messageWarning(...args),
    },
    ElMessageBox: {
      confirm: (...args: unknown[]) => mockConfirm(...args),
    },
  }
})

const STUBS = {
  PageSectionCard: {
    props: ['title'],
    template: '<div><slot name="actions" /><slot /></div>',
  },
  'el-button': true,
  'el-table': true,
  'el-table-column': true,
  'el-tag': true,
  'el-tooltip': { template: '<div><slot /></div>' },
  'el-dialog': { template: '<div><slot /><slot name="footer" /></div>' },
  'el-form': { template: '<form><slot /></form>' },
  'el-form-item': { template: '<div><slot /></div>' },
  'el-input': true,
  'el-alert': true,
  'el-checkbox': true,
}

const permissions: PermissionOut[] = [
  { code: 'auth:view', name: '权限设置-查看', group_name: '权限设置' },
  { code: 'auth:manage', name: '权限设置-管理', group_name: '权限设置' },
  { code: 'restock:view', name: '补货发起-查看', group_name: '补货发起' },
  { code: 'restock:operate', name: '补货发起-操作', group_name: '补货发起' },
]

const operatorRole: RoleOut = {
  id: 2,
  name: 'Operator',
  description: 'Operator role',
  is_superadmin: false,
  user_count: 1,
}

async function mountView() {
  const { default: View } = await import('../RoleConfigView.vue')
  const wrapper = shallowMount(View, { global: { stubs: STUBS } })
  await flushPromises()
  return wrapper
}

describe('RoleConfigView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockGetRoles.mockResolvedValue([operatorRole])
    mockGetPermissions.mockResolvedValue(permissions)
    mockGetRolePermissions.mockResolvedValue([])
    mockCreateRole.mockResolvedValue({ ...operatorRole, id: 3 })
    mockUpdateRole.mockResolvedValue(operatorRole)
    mockUpdateRolePermissions.mockResolvedValue(undefined)
    mockDeleteRole.mockResolvedValue(undefined)
    mockConfirm.mockResolvedValue(undefined)
    mockRouterReplace.mockResolvedValue(undefined)

    const auth = useAuthStore()
    auth.setAuth('test-token', {
      id: 10,
      username: 'tester',
      displayName: 'Tester',
      roleName: 'Operator',
      isSuperadmin: false,
      passwordIsDefault: false,
      permissions: ['auth:manage'],
    })
  })

  it('auto-selects auth:view when auth:manage is checked', async () => {
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      openEdit: (role: RoleOut) => Promise<void>
      toggleCode: (code: string, val: boolean) => void
      checkedCodes: Set<string>
    }

    await vm.openEdit(operatorRole)
    vm.toggleCode('auth:manage', true)

    expect(vm.checkedCodes.has('auth:manage')).toBe(true)
    expect(vm.checkedCodes.has('auth:view')).toBe(true)
  })

  it('confirms and clears auth after current role permissions change', async () => {
    mockGetRolePermissions.mockResolvedValue(['auth:view'])
    const wrapper = await mountView()
    const auth = useAuthStore()
    const vm = wrapper.vm as unknown as {
      openEdit: (role: RoleOut) => Promise<void>
      toggleCode: (code: string, val: boolean) => void
      handleSave: () => Promise<void>
    }

    await vm.openEdit(operatorRole)
    vm.toggleCode('auth:manage', true)
    await vm.handleSave()

    expect(mockConfirm).toHaveBeenCalled()
    expect(mockUpdateRolePermissions).toHaveBeenCalledWith(
      2,
      expect.arrayContaining(['auth:manage', 'auth:view']),
    )
    expect(auth.token).toBeNull()
    expect(mockRouterReplace).toHaveBeenCalledWith({ path: '/login' })
  })

  it('does not confirm or update permissions when permission set is unchanged', async () => {
    mockGetRolePermissions.mockResolvedValue(['auth:view', 'auth:manage'])
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      openEdit: (role: RoleOut) => Promise<void>
      handleSave: () => Promise<void>
    }

    await vm.openEdit(operatorRole)
    await vm.handleSave()

    expect(mockConfirm).not.toHaveBeenCalled()
    expect(mockUpdateRole).toHaveBeenCalledWith(2, {
      name: 'Operator',
      description: 'Operator role',
    })
    expect(mockUpdateRolePermissions).not.toHaveBeenCalled()
  })
})
