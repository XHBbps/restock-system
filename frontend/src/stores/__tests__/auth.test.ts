import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore, type UserInfo } from '../auth'

const mockUser: UserInfo = {
  id: 1,
  username: 'admin',
  displayName: 'Admin',
  roleName: '管理员',
  isSuperadmin: false,
  passwordIsDefault: false,
  permissions: ['inventory:read', 'restock:write'],
}

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('starts unauthenticated when localStorage empty', () => {
    const auth = useAuthStore()
    expect(auth.token).toBeNull()
    expect(auth.user).toBeNull()
    expect(auth.isAuthenticated).toBe(false)
  })

  it('hydrates token and user from localStorage on init', () => {
    localStorage.setItem('restock_token', 'stored-token')
    localStorage.setItem('restock_user', JSON.stringify(mockUser))
    setActivePinia(createPinia())
    const auth = useAuthStore()
    expect(auth.token).toBe('stored-token')
    expect(auth.user).toEqual(mockUser)
    expect(auth.isAuthenticated).toBe(true)
  })

  it('clears invalid stored user snapshot instead of crashing', () => {
    localStorage.setItem('restock_token', 'stored-token')
    localStorage.setItem('restock_user', '{invalid-json')

    setActivePinia(createPinia())
    const auth = useAuthStore()

    expect(auth.token).toBe('stored-token')
    expect(auth.user).toBeNull()
    expect(localStorage.getItem('restock_user')).toBeNull()
  })

  it('clears malformed stored user shape instead of using bad data', () => {
    localStorage.setItem('restock_user', JSON.stringify({ username: 'admin' }))

    setActivePinia(createPinia())
    const auth = useAuthStore()

    expect(auth.user).toBeNull()
    expect(localStorage.getItem('restock_user')).toBeNull()
  })

  it('setAuth updates state and localStorage', () => {
    const auth = useAuthStore()
    auth.setAuth('new-token', mockUser)
    expect(auth.token).toBe('new-token')
    expect(auth.user).toEqual(mockUser)
    expect(auth.isAuthenticated).toBe(true)
    expect(localStorage.getItem('restock_token')).toBe('new-token')
    expect(JSON.parse(localStorage.getItem('restock_user')!)).toEqual(mockUser)
  })

  it('clearAuth removes state and localStorage entries', () => {
    const auth = useAuthStore()
    auth.setAuth('temp', mockUser)
    auth.clearAuth()
    expect(auth.token).toBeNull()
    expect(auth.user).toBeNull()
    expect(auth.isAuthenticated).toBe(false)
    expect(localStorage.getItem('restock_token')).toBeNull()
    expect(localStorage.getItem('restock_user')).toBeNull()
  })

  it('hasPermission returns true for matching permission code', () => {
    const auth = useAuthStore()
    auth.setAuth('t', mockUser)
    expect(auth.hasPermission('inventory:read')).toBe(true)
    expect(auth.hasPermission('inventory:delete')).toBe(false)
  })

  it('hasPermission returns true for any code when superadmin', () => {
    const auth = useAuthStore()
    auth.setAuth('t', { ...mockUser, isSuperadmin: true, permissions: [] })
    expect(auth.hasPermission('anything')).toBe(true)
  })

  it('hasPermission returns false when no user', () => {
    const auth = useAuthStore()
    expect(auth.hasPermission('inventory:read')).toBe(false)
  })
})
