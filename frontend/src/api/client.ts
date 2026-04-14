// axios 封装：注入 Bearer + 401 重定向 + 403 权限提示 + 业务错误统一抛出
import { useAuthStore } from '@/stores/auth'
import axios, { AxiosError, type AxiosInstance } from 'axios'
import { ElMessage } from 'element-plus'

const client: AxiosInstance = axios.create({
  baseURL: '/',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
})

client.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers = config.headers ?? {}
    ;(config.headers as Record<string, string>).Authorization = `Bearer ${auth.token}`
  }
  return config
})

client.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      const auth = useAuthStore()
      auth.clearAuth()
      // 跳到登录
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    if (error.response?.status === 403) {
      ElMessage.error('权限不足，请联系管理员')
      const auth = useAuthStore()
      auth.restoreAuth() // fire-and-forget
    }
    return Promise.reject(error)
  }
)

export default client
