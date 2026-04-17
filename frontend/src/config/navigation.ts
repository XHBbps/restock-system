import type { Component } from 'vue'

import type { AppPageDefinition, AppPageNavCategory, AppPageSection } from '@/config/appPages'
import { appPages, navCategoryMeta } from '@/config/appPages'

export interface NavItem {
  to: string
  label: string
  icon: Component
  permission?: string
}

export interface NavSubCategory {
  label: string
  icon: Component
  permission?: string
  items: NavItem[]
}

export interface NavGroup {
  title: string
  children: (NavItem | NavSubCategory)[]
}

export function isSubCategory(child: NavItem | NavSubCategory): child is NavSubCategory {
  return 'items' in child
}

const sectionOrder: AppPageSection[] = ['HOME', 'RESTOCK', 'DATA', 'SETTINGS']

function toNavItem(page: AppPageDefinition): NavItem {
  return {
    to: `/${page.path}`,
    label: page.title,
    icon: page.icon,
    permission: page.permission,
  }
}

function getSectionChildren(section: AppPageSection): (NavItem | NavSubCategory)[] {
  const sectionPages = appPages.filter((page) => page.section === section)
  const directItems = sectionPages
    .filter((page) => !page.navCategory)
    .map(toNavItem)

  const categoryKeys = Array.from(
    new Set(
      sectionPages
        .map((page) => page.navCategory)
        .filter((value): value is AppPageNavCategory => Boolean(value)),
    ),
  )

  const subCategories = categoryKeys.map((categoryKey) => {
    const meta = navCategoryMeta[categoryKey]
    return {
      label: meta.label,
      icon: meta.icon,
      permission: meta.permission,
      items: sectionPages
        .filter((page) => page.navCategory === categoryKey)
        .map(toNavItem),
    } satisfies NavSubCategory
  })

  return [...directItems, ...subCategories]
}

export const navigationGroups: NavGroup[] = sectionOrder
  .map((section) => ({
    title: section,
    children: getSectionChildren(section),
  }))
  .filter((group) => group.children.length > 0)
