import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore } from '../auth'

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('starts unauthenticated when localStorage empty', () => {
    const auth = useAuthStore()
    expect(auth.token).toBeNull()
    expect(auth.isAuthenticated).toBe(false)
  })

  it('hydrates token from localStorage on init', () => {
    localStorage.setItem('restock_token', 'stored-token')
    // Re-create pinia so the store re-initializes with fresh localStorage
    setActivePinia(createPinia())
    const auth = useAuthStore()
    expect(auth.token).toBe('stored-token')
    expect(auth.isAuthenticated).toBe(true)
  })

  it('setToken updates state and localStorage', () => {
    const auth = useAuthStore()
    auth.setToken('new-token')
    expect(auth.token).toBe('new-token')
    expect(auth.isAuthenticated).toBe(true)
    expect(localStorage.getItem('restock_token')).toBe('new-token')
  })

  it('clearToken removes state and localStorage entry', () => {
    const auth = useAuthStore()
    auth.setToken('temp')
    auth.clearToken()
    expect(auth.token).toBeNull()
    expect(auth.isAuthenticated).toBe(false)
    expect(localStorage.getItem('restock_token')).toBeNull()
  })
})
