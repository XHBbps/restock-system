import { describe, expect, it, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
// Mock the auth API so restoreAuth won't make real requests
vi.mock('@/api/auth', () => ({
  me: vi.fn(),
}))

import { useAuthStore } from '@/stores/auth'
import router from '../index'

describe('router guard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('allows public routes without auth', async () => {
    // Navigate to login (public route) — should succeed without redirect
    await router.push('/login')
    expect(router.currentRoute.value.name).toBe('login')
  })

  it('redirects to login when unauthenticated on private route', async () => {
    const auth = useAuthStore()
    auth.clearAuth()
    await router.push('/workspace')
    expect(router.currentRoute.value.name).toBe('login')
  })
})
