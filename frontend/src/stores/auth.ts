import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { me as fetchMe } from '@/api/auth'
import { readStoredJson } from '@/utils/storage'

const TOKEN_KEY = 'restock_token'
const USER_KEY = 'restock_user'

export interface UserInfo {
  id: number
  username: string
  displayName: string
  roleName: string
  isSuperadmin: boolean
  passwordIsDefault: boolean
  permissions: string[]
}

function isUserInfo(value: unknown): value is UserInfo {
  if (!value || typeof value !== 'object') {
    return false
  }

  const raw = value as Record<string, unknown>
  return (
    typeof raw.id === 'number'
    && typeof raw.username === 'string'
    && typeof raw.displayName === 'string'
    && typeof raw.roleName === 'string'
    && typeof raw.isSuperadmin === 'boolean'
    && typeof raw.passwordIsDefault === 'boolean'
    && Array.isArray(raw.permissions)
    && raw.permissions.every((permission) => typeof permission === 'string')
  )
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<UserInfo | null>(
    readStoredJson<UserInfo | null>(USER_KEY, null, {
      guard: (value): value is UserInfo | null => isUserInfo(value),
    }),
  )

  const isAuthenticated = computed(() => !!token.value)

  function hasPermission(code: string): boolean {
    if (!user.value) return false
    return user.value.isSuperadmin || user.value.permissions.includes(code)
  }

  function setAuth(newToken: string, newUser: UserInfo) {
    token.value = newToken
    user.value = newUser
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem(USER_KEY, JSON.stringify(newUser))
  }

  function clearAuth() {
    token.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  let _restorePromise: Promise<void> | null = null

  async function restoreAuth(): Promise<void> {
    if (_restorePromise) return _restorePromise
    _restorePromise = _doRestore()
    try {
      await _restorePromise
    } finally {
      _restorePromise = null
    }
  }

  async function _doRestore(): Promise<void> {
    const resp = await fetchMe()
    user.value = _mapUserInfo(resp)
    localStorage.setItem(USER_KEY, JSON.stringify(user.value))
  }

  return { token, user, isAuthenticated, hasPermission, setAuth, clearAuth, restoreAuth }
})

export function _mapUserInfo(raw: Record<string, unknown>): UserInfo {
  return {
    id: typeof raw.id === 'number' ? raw.id : 0,
    username: String(raw.username ?? ''),
    displayName: String(raw.display_name ?? raw.username ?? ''),
    roleName: String(raw.role_name ?? ''),
    isSuperadmin: Boolean(raw.is_superadmin),
    passwordIsDefault: Boolean(raw.password_is_default),
    permissions: Array.isArray(raw.permissions) ? raw.permissions : [],
  }
}
