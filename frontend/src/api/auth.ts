// 鉴权 API 客户端
import client from './client'

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export async function login(password: string): Promise<LoginResponse> {
  const { data } = await client.post<LoginResponse>('/api/auth/login', { password })
  return data
}

export async function logout(): Promise<void> {
  await client.post('/api/auth/logout')
}

export async function me(): Promise<{ subject: string }> {
  const { data } = await client.get<{ subject: string }>('/api/auth/me')
  return data
}
