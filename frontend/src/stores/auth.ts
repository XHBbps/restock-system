// 鉴权 Pinia store：管理 token + 登录状态
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

const TOKEN_KEY = 'restock_token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))

  const isAuthenticated = computed(() => !!token.value)

  function setToken(newToken: string) {
    token.value = newToken
    localStorage.setItem(TOKEN_KEY, newToken)
  }

  function clearToken() {
    token.value = null
    localStorage.removeItem(TOKEN_KEY)
  }

  return { token, isAuthenticated, setToken, clearToken }
})
