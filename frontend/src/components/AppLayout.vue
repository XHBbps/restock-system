<template>
  <div class="app-layout">
    <aside class="sidebar" :class="{ 'sidebar-collapsed': sidebar.isCollapsed }">
      <div class="sidebar-brand">
        <div class="brand-mark">R</div>
        <template v-if="!sidebar.isCollapsed">
          <div class="brand-text">
            <div class="brand-name">Restock System</div>
            <div class="brand-meta">补货管理</div>
          </div>
        </template>
      </div>

      <nav class="nav">
        <div v-for="(group, gi) in navigationGroups" :key="group.title" class="nav-group">
          <!-- Divider between groups (collapsed only) -->
          <div v-if="gi > 0 && sidebar.isCollapsed" class="nav-group-divider" />

          <!-- Group title (expanded only) -->
          <div v-if="!sidebar.isCollapsed" class="nav-group-title">{{ group.title }}</div>

          <template v-for="child in group.children" :key="'items' in child ? child.label : child.to">
            <!-- SubCategory -->
            <template v-if="isSubCategory(child)">
              <!-- EXPANDED: collapsible toggle + items -->
              <template v-if="!sidebar.isCollapsed">
                <button
                  class="nav-subcategory-toggle"
                  @click="sidebar.toggleCategory(child.label)"
                >
                  <span>{{ child.label }}</span>
                  <ChevronRight
                    class="nav-subcategory-chevron"
                    :class="{ 'nav-subcategory-chevron-open': sidebar.isCategoryExpanded(child.label) }"
                    :size="12"
                  />
                </button>
                <div v-if="sidebar.isCategoryExpanded(child.label)" class="nav-subcategory-items">
                  <RouterLink
                    v-for="item in child.items"
                    :key="item.to"
                    :to="item.to"
                    class="nav-item"
                    active-class="nav-item-active"
                  >
                    <component :is="item.icon" class="nav-item-icon" :size="16" />
                    <span class="nav-item-label">{{ item.label }}</span>
                  </RouterLink>
                </div>
              </template>

              <!-- COLLAPSED: icon with hover popover -->
              <div
                v-else
                class="nav-popover-wrapper"
                @mouseenter="showPopover($event, child.label)"
                @mouseleave="hidePopover"
              >
                <div class="nav-item nav-item-collapsed" :title="child.label">
                  <component :is="child.icon" class="nav-item-icon" :size="18" />
                </div>
              </div>
            </template>

            <!-- Direct NavItem -->
            <RouterLink
              v-else
              :to="child.to"
              class="nav-item"
              :class="{ 'nav-item-collapsed': sidebar.isCollapsed }"
              active-class="nav-item-active"
              :title="sidebar.isCollapsed ? child.label : undefined"
            >
              <component :is="child.icon" class="nav-item-icon" :size="sidebar.isCollapsed ? 18 : 16" />
              <span v-if="!sidebar.isCollapsed" class="nav-item-label">{{ child.label }}</span>
            </RouterLink>
          </template>
        </div>
      </nav>

      <div class="sidebar-footer">
        <template v-if="!sidebar.isCollapsed">
          <div class="user-meta">
            <div class="user-name">采购控制台</div>
            <div class="user-role">内部系统</div>
          </div>
        </template>
        <button class="logout-btn" title="退出登录" @click="handleLogout">
          <LogOut :size="14" />
        </button>
      </div>
    </aside>

    <!-- Fixed popover for collapsed sub-category hover -->
    <Teleport to="body">
      <div
        v-if="popover.visible"
        class="nav-popover"
        :style="{ top: popover.top + 'px', left: popover.left + 'px' }"
        @mouseenter="cancelHidePopover"
        @mouseleave="hidePopover"
      >
        <div class="nav-popover-title">{{ popover.label }}</div>
        <template v-for="group in navigationGroups" :key="group.title">
          <template v-for="child in group.children" :key="'items' in child ? child.label : child.to">
            <template v-if="isSubCategory(child) && child.label === popover.label">
              <RouterLink
                v-for="item in child.items"
                :key="item.to"
                :to="item.to"
                class="nav-popover-item"
                active-class="nav-popover-item-active"
                @click="hidePopover"
              >
                {{ item.label }}
              </RouterLink>
            </template>
          </template>
        </template>
      </div>
    </Teleport>

    <main class="main">
      <header class="topbar">
        <div class="topbar-left">
          <button class="collapse-btn" :title="sidebar.isCollapsed ? '展开侧栏' : '收起侧栏'" @click="sidebar.toggleCollapse()">
            <PanelLeftOpen v-if="sidebar.isCollapsed" :size="16" />
            <PanelLeftClose v-else :size="16" />
          </button>
          <div class="breadcrumb">
            <RouterLink to="/workspace" class="breadcrumb-root">Restock</RouterLink>
            <ChevronRight class="breadcrumb-sep" :size="12" />
            <span class="breadcrumb-section">{{ currentSection }}</span>
            <ChevronRight class="breadcrumb-sep" :size="12" />
            <span class="breadcrumb-current">{{ currentTitle }}</span>
          </div>
        </div>
        <div class="topbar-right">
          <span class="badge-env">Dashboard</span>
          <span class="badge-version">v0.1.0</span>
        </div>
      </header>

      <div class="content">
        <div class="content-shell">
          <RouterView />
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { logout } from '@/api/auth'
import { isSubCategory, navigationGroups } from '@/config/navigation'
import { useAuthStore } from '@/stores/auth'
import { useSidebarStore } from '@/stores/sidebar'
import { ChevronRight, LogOut, PanelLeftClose, PanelLeftOpen } from 'lucide-vue-next'
import { computed, onMounted, reactive, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const sidebar = useSidebarStore()

const currentTitle = computed(() => (route.meta.title as string) || '总览')
const currentSection = computed(() => (route.meta.section as string) || '工作台')

// Popover state for collapsed sub-category hover
const popover = reactive({ visible: false, label: '', top: 0, left: 0 })
let hideTimer: ReturnType<typeof setTimeout> | null = null

function showPopover(event: MouseEvent, label: string) {
  if (hideTimer) { clearTimeout(hideTimer); hideTimer = null }
  const el = event.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  popover.top = rect.top
  popover.left = rect.right + 6
  popover.label = label
  popover.visible = true
}

function hidePopover() {
  hideTimer = setTimeout(() => { popover.visible = false }, 100)
}

function cancelHidePopover() {
  if (hideTimer) { clearTimeout(hideTimer); hideTimer = null }
}

function autoExpandActiveCategory() {
  for (const group of navigationGroups) {
    for (const child of group.children) {
      if (isSubCategory(child)) {
        for (const item of child.items) {
          if (route.path.startsWith(item.to)) {
            sidebar.ensureCategoryExpanded(child.label)
            return
          }
        }
      }
    }
  }
}

onMounted(autoExpandActiveCategory)
watch(() => route.path, autoExpandActiveCategory)

async function handleLogout(): Promise<void> {
  try {
    await logout()
  } finally {
    auth.clearToken()
    router.replace('/login')
  }
}
</script>

<style lang="scss" scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  background: $color-bg-base;
  color: $color-text-primary;
}

.sidebar {
  position: relative;
  position: sticky;
  top: 0;
  width: 256px;
  height: 100vh;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-self: flex-start;
  background: $color-bg-card;
  border-right: 1px solid $color-border-default;
  overflow: hidden;
  transition: width 300ms ease;
}

.sidebar-collapsed {
  width: 64px;
}

.sidebar-brand {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $space-3;
  padding: $space-4;
  height: $layout-topbar-height;
  background: $color-bg-card;
  border-bottom: 1px solid $color-border-default;
}

.sidebar-collapsed .sidebar-brand {
  justify-content: center;
  padding: $space-3;
}

.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: $radius-lg;
  background: $color-brand-primary;
  color: $color-brand-primary-fg;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: $font-weight-bold;
}

.brand-name {
  font-weight: $font-weight-semibold;
}

.brand-meta {
  font-size: $font-size-xs;
  color: $color-text-secondary;
}

.nav {
  flex: 1;
  padding: $space-3;
  padding-bottom: calc($space-4 * 2 + 48px);
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
  scrollbar-color: $color-border-default transparent;
}


.nav::-webkit-scrollbar {
  width: 8px;
}

.nav::-webkit-scrollbar-track {
  background: transparent;
}

.nav::-webkit-scrollbar-thumb {
  background: $color-border-default;
  border-radius: $radius-pill;
}

.nav::-webkit-scrollbar-thumb:hover {
  background: $color-text-disabled;
}

.nav-group + .nav-group {
  margin-top: $space-4;
}

.nav-group-title {
  padding: 0 $space-3 $space-2;
  color: $color-text-secondary;
  font-size: 11px;
  font-weight: $font-weight-semibold;
  letter-spacing: $tracking-wider;
  text-transform: uppercase;
}

.nav-subcategory-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: $space-2 $space-3 $space-1;
  margin-top: $space-2;
  border: none;
  background: transparent;
  color: $color-text-disabled;
  font-size: 11px;
  font-weight: $font-weight-medium;
  cursor: pointer;
  text-align: left;

  &:hover {
    color: $color-text-secondary;
  }
}

.nav-group .nav-subcategory-toggle:first-child {
  margin-top: 0;
}

.nav-subcategory-chevron {
  transition: transform 200ms ease;
}

.nav-subcategory-chevron-open {
  transform: rotate(90deg);
}

.sidebar-collapsed .nav-group-title {
  display: none;
}

.nav-group-divider {
  height: 1px;
  margin: $space-2 $space-3;
  background: $color-border-default;
}

.nav-item-collapsed {
  justify-content: center;
  padding: 10px 0;
}

.nav-popover-wrapper {
  position: relative;
}


.sidebar-collapsed .nav-item-icon {
  color: $color-text-primary;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: $space-3;
  padding: 9px $space-3;
  border-radius: $radius-md;
  color: $color-text-primary;
  text-decoration: none;
  transition: $transition-fast;

  &:hover {
    background: $color-bg-subtle;
  }
}

.nav-item-active {
  background: $color-bg-subtle;
  font-weight: $font-weight-semibold;
}

.nav-item-icon {
  flex-shrink: 0;
  color: $color-text-secondary;
}

.sidebar-footer {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-3;
  padding: $space-4;
  background: $color-bg-card;
  border-top: 1px solid $color-border-default;
  box-shadow: 0 -8px 24px rgba(15, 23, 42, 0.04);
}

.user-name {
  font-weight: $font-weight-semibold;
}

.user-role {
  font-size: $font-size-xs;
  color: $color-text-secondary;
}

.logout-btn {
  width: 32px;
  height: 32px;
  border: 1px solid transparent;
  border-radius: $radius-md;
  background: transparent;
  color: $color-text-secondary;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;

  &:hover {
    background: $color-bg-subtle;
    border-color: $color-border-default;
    color: $color-text-primary;
  }
}

.sidebar-collapsed .sidebar-footer {
  justify-content: center;
}

.sidebar-collapsed .logout-btn {
  margin: 0 auto;
}

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  height: $layout-topbar-height;
  padding: 0 $space-6;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid $color-border-default;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: $space-3;
}

.collapse-btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: $radius-md;
  background: transparent;
  color: $color-text-secondary;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &:hover {
    background: $color-bg-subtle;
    color: $color-text-primary;
  }
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: $space-2;
  font-size: $font-size-sm;
}

.breadcrumb-root {
  color: $color-text-secondary;
  text-decoration: none;
}

.breadcrumb-section {
  color: $color-text-secondary;
}

.breadcrumb-current {
  font-weight: $font-weight-semibold;
}

.breadcrumb-sep {
  color: $color-text-disabled;
}

.topbar-right {
  display: flex;
  gap: $space-2;
  align-items: center;
}

.badge-env,
.badge-version {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 10px;
  border-radius: $radius-md;
  border: 1px solid $color-border-default;
  background: $color-bg-card;
  color: $color-text-secondary;
  font-size: 11px;
}

.content {
  flex: 1;
  padding: $layout-content-padding;
  overflow-y: auto;
}

.content-shell {
  max-width: 1480px;
  margin: 0 auto;
}

@media (max-width: 1100px) {
  .sidebar:not(.sidebar-collapsed) {
    width: 232px;
  }
}

@media (max-width: 900px) {
  .topbar {
    padding: 0 $space-4;
  }

  .content {
    padding: $space-4;
  }
}
</style>

<style lang="scss">
/* Non-scoped: popover is teleported to body */
.nav-popover {
  position: fixed;
  z-index: 2000;
  min-width: 160px;
  padding: $space-2;
  background: $color-bg-card;
  border: 1px solid $color-border-default;
  border-radius: $radius-lg;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.12);
}

.nav-popover-title {
  padding: $space-1 $space-3;
  font-size: 11px;
  font-weight: $font-weight-semibold;
  color: $color-text-secondary;
  text-transform: uppercase;
  letter-spacing: $tracking-wider;
}

.nav-popover-item {
  display: block;
  padding: 8px $space-3;
  border-radius: $radius-md;
  color: $color-text-primary;
  text-decoration: none;
  font-size: $font-size-sm;
  transition: background 150ms ease;

  &:hover {
    background: $color-bg-subtle;
  }
}

.nav-popover-item-active {
  font-weight: $font-weight-semibold;
  background: $color-bg-subtle;
}
</style>
