// 鉴权 Pinia store：管理 token + 用户信息 + 权限
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { me as fetchMe } from '@/api/auth'

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

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))

  // Restore user from localStorage snapshot (avoid flicker on refresh)
  const _savedUser = localStorage.getItem(USER_KEY)
  const user = ref<UserInfo | null>(_savedUser ? JSON.parse(_savedUser) : null)

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

  // Promise dedup for restoreAuth
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

/** Map backend snake_case response to camelCase UserInfo */
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
