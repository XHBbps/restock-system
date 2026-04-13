import { describe, expect, it } from 'vitest'
import type { RouteLocationNormalized } from 'vue-router'

import { authGuard } from '../index'

function makeRoute(overrides: Partial<RouteLocationNormalized> = {}): RouteLocationNormalized {
  return {
    path: '/x',
    fullPath: '/x',
    name: 'x',
    params: {},
    query: {},
    hash: '',
    matched: [],
    meta: {},
    redirectedFrom: undefined,
    ...overrides,
  } as RouteLocationNormalized
}

describe('authGuard', () => {
  it('allows public routes without auth', () => {
    const route = makeRoute({ meta: { public: true } })
    expect(authGuard(route, false)).toBe(true)
  })

  it('allows private routes when authenticated', () => {
    const route = makeRoute({ meta: {} })
    expect(authGuard(route, true)).toBe(true)
  })

  it('redirects to login when unauthenticated on private route', () => {
    const route = makeRoute({ fullPath: '/suggestions/1', meta: {} })
    const result = authGuard(route, false)
    expect(result).toEqual({
      name: 'login',
      query: { redirect: '/suggestions/1' },
    })
  })
})
