import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useSidebarStore } from '../sidebar'

describe('useSidebarStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('hydrates expanded categories from localStorage', () => {
    localStorage.setItem('sidebar_expanded_cats', JSON.stringify(['基础数据', '业务数据']))

    setActivePinia(createPinia())
    const sidebar = useSidebarStore()

    expect(sidebar.isCategoryExpanded('基础数据')).toBe(true)
    expect(sidebar.isCategoryExpanded('业务数据')).toBe(true)
  })

  it('clears invalid expanded categories JSON instead of crashing', () => {
    localStorage.setItem('sidebar_expanded_cats', '{invalid-json')

    setActivePinia(createPinia())
    const sidebar = useSidebarStore()

    expect(sidebar.expandedCategories.size).toBe(0)
    expect(localStorage.getItem('sidebar_expanded_cats')).toBeNull()
  })

  it('clears malformed expanded categories shape', () => {
    localStorage.setItem('sidebar_expanded_cats', JSON.stringify({ label: '基础数据' }))

    setActivePinia(createPinia())
    const sidebar = useSidebarStore()

    expect(sidebar.expandedCategories.size).toBe(0)
    expect(localStorage.getItem('sidebar_expanded_cats')).toBeNull()
  })
})
