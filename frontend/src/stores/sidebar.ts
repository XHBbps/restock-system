import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

import { isStringArray, readStoredJson } from '@/utils/storage'

const COLLAPSED_KEY = 'sidebar_collapsed'
const EXPANDED_CATS_KEY = 'sidebar_expanded_cats'

export const useSidebarStore = defineStore('sidebar', () => {
  const isCollapsed = ref(localStorage.getItem(COLLAPSED_KEY) === 'true')
  const expandedCategories = ref<Set<string>>(
    new Set(readStoredJson<string[]>(EXPANDED_CATS_KEY, [], { guard: isStringArray })),
  )

  watch(isCollapsed, (val) => localStorage.setItem(COLLAPSED_KEY, String(val)))
  watch(
    expandedCategories,
    (val) => localStorage.setItem(EXPANDED_CATS_KEY, JSON.stringify([...val])),
    { deep: true },
  )

  function toggleCollapse() {
    isCollapsed.value = !isCollapsed.value
  }

  function toggleCategory(label: string) {
    if (expandedCategories.value.has(label)) {
      expandedCategories.value.delete(label)
    } else {
      expandedCategories.value.add(label)
    }
  }

  function ensureCategoryExpanded(label: string) {
    expandedCategories.value.add(label)
  }

  function isCategoryExpanded(label: string): boolean {
    return expandedCategories.value.has(label)
  }

  return { isCollapsed, expandedCategories, toggleCollapse, toggleCategory, ensureCategoryExpanded, isCategoryExpanded }
})
