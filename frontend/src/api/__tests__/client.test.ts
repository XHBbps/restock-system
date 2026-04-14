import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { AxiosError, InternalAxiosRequestConfig } from 'axios'

import client from '../client'
import { useAuthStore, type UserInfo } from '@/stores/auth'

type RequestHandler = {
  fulfilled: (c: InternalAxiosRequestConfig) => InternalAxiosRequestConfig
}
type ResponseHandler = {
  fulfilled: (r: unknown) => unknown
  rejected: (e: AxiosError) => Promise<unknown>
}

function getRequestHandler(): RequestHandler {
  return (client.interceptors.request as unknown as { handlers: RequestHandler[] }).handlers[0]
}

function getResponseHandler(): ResponseHandler {
  return (client.interceptors.response as unknown as { handlers: ResponseHandler[] }).handlers[0]
}

const dummyUser: UserInfo = {
  id: 1,
  username: 'test',
  displayName: 'Test',
  roleName: 'viewer',
  isSuperadmin: false,
  passwordIsDefault: false,
  permissions: [],
}

describe('api/client interceptors', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('injects Bearer token when authenticated', () => {
    const auth = useAuthStore()
    auth.setAuth('abc123', dummyUser)

    const config = { headers: {} } as InternalAxiosRequestConfig
    const result = getRequestHandler().fulfilled(config)
    expect((result.headers as Record<string, string>).Authorization).toBe('Bearer abc123')
  })

  it('does not inject Authorization when unauthenticated', () => {
    const config = { headers: {} } as InternalAxiosRequestConfig
    const result = getRequestHandler().fulfilled(config)
    expect((result.headers as Record<string, string>).Authorization).toBeUndefined()
  })

  it('clears auth on 401 response', async () => {
    const auth = useAuthStore()
    auth.setAuth('willbecleared', dummyUser)

    // Stub window.location to a non-login path so redirect branch executes safely
    delete (window as unknown as Record<string, unknown>).location
    ;(window as unknown as Record<string, unknown>).location = { pathname: '/dashboard', href: '' }

    const error = {
      response: { status: 401 },
      isAxiosError: true,
    } as unknown as AxiosError

    await expect(getResponseHandler().rejected(error)).rejects.toBe(error)
    expect(auth.token).toBeNull()
    expect(auth.user).toBeNull()
  })

  it('does not clear auth on non-401 errors', async () => {
    const auth = useAuthStore()
    auth.setAuth('keepme', dummyUser)

    const error = {
      response: { status: 500 },
      isAxiosError: true,
    } as unknown as AxiosError

    await expect(getResponseHandler().rejected(error)).rejects.toBe(error)
    expect(auth.token).toBe('keepme')
  })
})
