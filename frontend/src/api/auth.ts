// 鉴权 API 客户端
import client from './client'

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: Record<string, unknown>
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const { data } = await client.post<LoginResponse>('/api/auth/login', { username, password })
  return data
}

export async function logout(): Promise<void> {
  await client.post('/api/auth/logout')
}

export async function me(): Promise<Record<string, unknown>> {
  const { data } = await client.get<Record<string, unknown>>('/api/auth/me')
  return data
}

export async function changeOwnPassword(oldPassword: string, newPassword: string): Promise<void> {
  await client.put('/api/auth/users/me/password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}
