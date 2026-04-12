import type { AxiosError } from 'axios'

export function getActionErrorMessage(error: unknown, fallback: string): string {
  const axiosError = error as AxiosError<{
    message?: string
    detail?: Array<{ loc?: Array<string | number>; msg?: string }> | string
  }>

  if (!axiosError.response) {
    return '后端服务不可用，请确认后端已启动且前端代理目标配置正确。'
  }

  if (typeof axiosError.response.data?.message === 'string' && axiosError.response.data.message.trim()) {
    return axiosError.response.data.message
  }

  if (Array.isArray(axiosError.response.data?.detail) && axiosError.response.data.detail.length > 0) {
    const firstError = axiosError.response.data.detail[0]
    const loc = Array.isArray(firstError.loc) ? firstError.loc.at(-1) : undefined
    if (typeof firstError.msg === 'string' && firstError.msg.trim()) {
      if (typeof loc === 'string' && loc.trim()) {
        return `${loc}：${firstError.msg}`
      }
      return firstError.msg
    }
  }

  if (typeof axiosError.response.data?.detail === 'string' && axiosError.response.data.detail.trim()) {
    return axiosError.response.data.detail
  }

  if (axiosError.response.status >= 500) {
    return '后端接口异常，请检查后端日志或确认开发代理目标是否可用。'
  }

  return fallback
}
