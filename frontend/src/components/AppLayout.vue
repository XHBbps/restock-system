<template>
  <div class="app-layout">
    <!-- ================== Sidebar (shadcn dashboard shell) ================== -->
    <aside class="sidebar">
      <!-- Brand -->
      <div class="sidebar-brand">
        <div class="brand-mark">R</div>
        <div class="brand-text">
          <div class="brand-name">Restock</div>
          <div class="brand-meta">Sellfox replenishment</div>
        </div>
      </div>

      <!-- Search trigger (visual only for now) -->
      <div class="sidebar-search">
        <span class="search-icon">⌕</span>
        <span class="search-placeholder">Search…</span>
        <kbd class="kbd">⌘K</kbd>
      </div>

      <!-- Nav -->
      <nav class="nav">
        <div v-for="group in menuGroups" :key="group.title" class="nav-group">
          <div class="nav-group-title">{{ group.title }}</div>
          <RouterLink
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="nav-item"
            active-class="nav-item-active"
          >
            <component :is="item.icon" class="nav-item-icon" />
            <span class="nav-item-label">{{ item.label }}</span>
          </RouterLink>
        </div>
      </nav>

      <!-- Footer -->
      <div class="sidebar-footer">
        <div class="user-row">
          <div class="user-avatar">采</div>
          <div class="user-meta">
            <div class="user-name">采购员</div>
            <div class="user-role">Owner</div>
          </div>
          <button class="logout-btn" title="登出" @click="handleLogout">
            <IconLogout />
          </button>
        </div>
      </div>
    </aside>

    <!-- ================== Main ================== -->
    <main class="main">
      <!-- Topbar with breadcrumb -->
      <header class="topbar">
        <div class="breadcrumb">
          <RouterLink to="/" class="breadcrumb-root">Restock</RouterLink>
          <IconChevronRight class="breadcrumb-sep" />
          <span class="breadcrumb-current">{{ currentTitle }}</span>
        </div>
        <div class="topbar-right">
          <span class="badge-env">v0.1.0 · DEV</span>
          <div class="topbar-divider" />
          <button class="topbar-btn" title="通知">
            <IconBell />
          </button>
        </div>
      </header>

      <div class="content">
        <RouterView />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { logout } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { computed, h } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

// ============ Inline SVG icons (Lucide-style, 16x16 stroke) ============
const svgBase = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  'stroke-width': 2,
  'stroke-linecap': 'round',
  'stroke-linejoin': 'round'
}

const IconClipboard = () =>
  h(
    'svg',
    { ...svgBase, width: 16, height: 16 },
    [
      h('rect', { x: 8, y: 2, width: 8, height: 4, rx: 1 }),
      h('path', {
        d: 'M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2'
      })
    ]
  )

const IconHistory = () =>
  h('svg', { ...svgBase, width: 16, height: 16 }, [
    h('path', { d: 'M3 12a9 9 0 1 0 3-6.7L3 8' }),
    h('path', { d: 'M3 3v5h5' }),
    h('path', { d: 'M12 7v5l4 2' })
  ])

const IconPackage = () =>
  h('svg', { ...svgBase, width: 16, height: 16 }, [
    h('path', {
      d: 'm7.5 4.27 9 5.15M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z'
    }),
    h('path', { d: 'm3.3 7 8.7 5 8.7-5' }),
    h('path', { d: 'M12 22V12' })
  ])

const IconSettings = () =>
  h('svg', { ...svgBase, width: 16, height: 16 }, [
    h('path', {
      d: 'M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z'
    }),
    h('circle', { cx: 12, cy: 12, r: 3 })
  ])

const IconWarehouse = () =>
  h('svg', { ...svgBase, width: 16, height: 16 }, [
    h('path', { d: 'M22 8.35V20a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8.35A2 2 0 0 1 3.26 6.5l8-3.2a2 2 0 0 1 1.48 0l8 3.2A2 2 0 0 1 22 8.35Z' }),
    h('path', { d: 'M6 18h12' }),
    h('path', { d: 'M6 14h12' }),
    h('rect', { width: 12, height: 12, x: 6, y: 10 })
  ])

const IconMail = () =>
  h('svg', { ...svgBase, width: 16, height: 16 }, [
    h('rect', { width: 20, height: 16, x: 2, y: 4, rx: 2 }),
    h('path', { d: 'm22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7' })
  ])

const IconStore = () =>
  h('svg', { ...svgBase, width: 16, height: 16 }, [
    h('path', { d: 'm2 7 4.41-4.41A2 2 0 0 1 7.83 2h8.34a2 2 0 0 1 1.42.59L22 7' }),
    h('path', { d: 'M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8' }),
    h('path', { d: 'M15 22v-4a2 2 0 0 0-2-2h-2a2 2 0 0 0-2 2v4' }),
    h('path', { d: 'M2 7h20' }),
    h('path', { d: 'M22 7v3a2 2 0 0 1-2 2a2.7 2.7 0 0 1-1.59-.63.5.5 0 0 0-.82 0A2.7 2.7 0 0 1 16 12a2.7 2.7 0 0 1-1.59-.63.5.5 0 0 0-.82 0A2.7 2.7 0 0 1 12 12a2.7 2.7 0 0 1-1.59-.63.5.5 0 0 0-.82 0A2.7 2.7 0 0 1 8 12a2.7 2.7 0 0 1-1.59-.63.5.5 0 0 0-.82 0A2.7 2.7 0 0 1 4 12a2 2 0 0 1-2-2V7' })
  ])

const IconBoxes = () =>
  h('svg', { ...svgBase, width: 16, height: 16 }, [
    h('path', { d: 'M2.97 12.92A2 2 0 0 0 2 14.63v3.24a2 2 0 0 0 .97 1.71l3 1.8a2 2 0 0 0 2.06 0L12 19v-5.5l-5-3-4.03 2.42Z' }),
    h('path', { d: 'm7 16.5-4.74-2.85' }),
    h('path', { d: 'm7 16.5 5-3' }),
    h('path', { d: 'M7 16.5v5.17' }),
    h('path', { d: 'M12 13.5V19l3.97 2.38a2 2 0 0 0 2.06 0l3-1.8a2 2 0 0 0 .97-1.71v-3.24a2 2 0 0 0-.97-1.71L17 10.5l-5 3Z' }),
    h('path', { d: 'm17 16.5-5-3' }),
    h('path', { d: 'm17 16.5 4.74-2.85' }),
    h('path', { d: 'M17 16.5v5.17' }),
    h('path', { d: 'M7.97 4.42A2 2 0 0 0 7 6.13v4.37l5 3 5-3V6.13a2 2 0 0 0-.97-1.71l-3-1.8a2 2 0 0 0-2.06 0l-3 1.8Z' }),
    h('path', { d: 'M12 8 7.26 5.15' }),
    h('path', { d: 'm12 8 4.74-2.85' }),
    h('path', { d: 'M12 13.5V8' })
  ])

const IconActivity = () =>
  h('svg', { ...svgBase, width: 16, height: 16 }, [
    h('path', { d: 'M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.5.5 0 0 1-.92 0L9.24 2.18a.5.5 0 0 0-.92 0l-2.35 8.36A2 2 0 0 1 4.05 12H2' })
  ])

const IconPlay = () =>
  h('svg', { ...svgBase, width: 16, height: 16 }, [
    h('polygon', { points: '6 3 20 12 6 21 6 3' })
  ])

const IconChevronRight = () =>
  h('svg', { ...svgBase, width: 12, height: 12 }, [
    h('path', { d: 'm9 18 6-6-6-6' })
  ])

const IconBell = () =>
  h('svg', { ...svgBase, width: 16, height: 16 }, [
    h('path', {
      d: 'M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9'
    }),
    h('path', { d: 'M10.3 21a1.94 1.94 0 0 0 3.4 0' })
  ])

const IconLogout = () =>
  h('svg', { ...svgBase, width: 14, height: 14 }, [
    h('path', { d: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4' }),
    h('polyline', { points: '16 17 21 12 16 7' }),
    h('line', { x1: 21, x2: 9, y1: 12, y2: 12 })
  ])

// ============ Routing ============
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const currentTitle = computed(() => (route.meta.title as string) || '')

const menuGroups = [
  {
    title: 'Replenish',
    items: [
      { to: '/suggestions', icon: IconClipboard, label: '当前建议单' },
      { to: '/history', icon: IconHistory, label: '历史记录' }
    ]
  },
  {
    title: 'Config',
    items: [
      { to: '/config/sku', icon: IconPackage, label: 'SKU 配置' },
      { to: '/config/global', icon: IconSettings, label: '全局参数' },
      { to: '/config/warehouse', icon: IconWarehouse, label: '仓库与国家' },
      { to: '/config/zipcode', icon: IconMail, label: '邮编规则' },
      { to: '/config/shop', icon: IconStore, label: '店铺管理' }
    ]
  },
  {
    title: 'Observability',
    items: [
      { to: '/monitor/overstock', icon: IconBoxes, label: '积压提示' },
      { to: '/monitor/api', icon: IconActivity, label: '接口监控' }
    ]
  },
  {
    title: 'Operations',
    items: [{ to: '/tasks/manual', icon: IconPlay, label: '手动同步/计算' }]
  }
]

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

// ============ Sidebar ============
.sidebar {
  width: $layout-sidebar-width;
  flex-shrink: 0;
  background: $color-bg-card;
  border-right: 1px solid $color-border-default;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: $space-3;
  padding: $space-4 $space-4;
  height: $layout-topbar-height;
  border-bottom: 1px solid $color-border-default;

  .brand-mark {
    width: 32px;
    height: 32px;
    border-radius: $radius-md;
    background: $color-brand-primary;
    color: $color-brand-primary-fg;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: $font-family-mono;
    font-weight: $font-weight-bold;
    font-size: $font-size-md;
    flex-shrink: 0;
    letter-spacing: -0.05em;
  }
  .brand-text {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .brand-name {
    font-size: $font-size-sm;
    font-weight: $font-weight-semibold;
    color: $color-text-primary;
    letter-spacing: $tracking-tight;
    line-height: 1.2;
  }
  .brand-meta {
    font-size: 11px;
    color: $color-text-secondary;
    letter-spacing: $tracking-normal;
    margin-top: 2px;
  }
}

.sidebar-search {
  display: flex;
  align-items: center;
  gap: $space-2;
  margin: $space-3 $space-3;
  padding: 0 $space-3;
  height: 32px;
  border: 1px solid $color-border-default;
  border-radius: $radius-md;
  background: $color-bg-card;
  color: $color-text-secondary;
  font-size: $font-size-xs;
  cursor: text;
  transition: $transition-fast;

  &:hover {
    background: $color-bg-subtle;
  }

  .search-icon {
    font-size: 14px;
    opacity: 0.7;
  }
  .search-placeholder {
    flex: 1;
    color: $color-text-disabled;
  }
}

.kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 20px;
  min-width: 28px;
  padding: 0 5px;
  border: 1px solid $color-border-default;
  border-radius: $radius-sm;
  background: $color-bg-card;
  color: $color-text-secondary;
  font-family: $font-family-mono;
  font-size: 10px;
  line-height: 1;
  letter-spacing: 0;
}

.nav {
  flex: 1;
  overflow-y: auto;
  padding: $space-2 $space-3 $space-4;
}

.nav-group + .nav-group {
  margin-top: $space-4;
}

.nav-group-title {
  font-size: 11px;
  color: $color-text-secondary;
  font-weight: $font-weight-semibold;
  letter-spacing: $tracking-wider;
  text-transform: uppercase;
  padding: 0 $space-3 $space-2;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: $space-3;
  padding: 6px $space-3;
  margin-bottom: 2px;
  border-radius: $radius-md;
  color: $color-text-primary;
  text-decoration: none;
  font-size: $font-size-sm;
  font-weight: $font-weight-medium;
  transition: $transition-fast;
  position: relative;

  &:hover {
    background: $color-bg-subtle;
    color: $color-text-primary;
  }
}

// shadcn authentic: bg-accent text-accent-foreground, no border strip
.nav-item-active {
  background: $color-bg-subtle !important;
  color: $color-text-primary !important;
  font-weight: $font-weight-semibold !important;
}

.nav-item-icon {
  flex-shrink: 0;
  color: $color-text-secondary;
  opacity: 0.85;

  .nav-item-active & {
    color: $color-text-primary;
    opacity: 1;
  }
}

.sidebar-footer {
  border-top: 1px solid $color-border-default;
  padding: $space-3 $space-4;
}

.user-row {
  display: flex;
  align-items: center;
  gap: $space-3;

  .user-avatar {
    width: 32px;
    height: 32px;
    border-radius: $radius-pill;
    background: $color-bg-subtle;
    border: 1px solid $color-border-default;
    color: $color-text-primary;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: $font-size-sm;
    font-weight: $font-weight-semibold;
    flex-shrink: 0;
  }

  .user-meta {
    flex: 1;
    min-width: 0;
  }
  .user-name {
    font-size: $font-size-sm;
    font-weight: $font-weight-semibold;
    color: $color-text-primary;
    line-height: 1.2;
  }
  .user-role {
    font-size: 11px;
    color: $color-text-secondary;
    margin-top: 1px;
  }
}

.logout-btn {
  width: 32px;
  height: 32px;
  border-radius: $radius-md;
  border: 1px solid transparent;
  background: transparent;
  color: $color-text-secondary;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: $transition-fast;

  &:hover {
    background: $color-bg-subtle;
    border-color: $color-border-default;
    color: $color-text-primary;
  }
}

// ============ Main ============
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: $color-bg-base;
}

.topbar {
  height: $layout-topbar-height;
  background: $color-bg-card;
  border-bottom: 1px solid $color-border-default;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 $space-6;
  flex-shrink: 0;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: $space-2;
  font-size: $font-size-sm;

  .breadcrumb-root {
    color: $color-text-secondary;
    text-decoration: none;
    font-weight: $font-weight-medium;
    transition: color $transition-fast;
    &:hover {
      color: $color-text-primary;
    }
  }
  .breadcrumb-sep {
    color: $color-text-disabled;
    flex-shrink: 0;
  }
  .breadcrumb-current {
    color: $color-text-primary;
    font-weight: $font-weight-semibold;
    letter-spacing: $tracking-tight;
  }
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: $space-3;
}

.badge-env {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 10px;
  border-radius: $radius-md;
  border: 1px solid $color-border-default;
  background: $color-bg-subtle;
  color: $color-text-secondary;
  font-size: 11px;
  font-family: $font-family-mono;
  letter-spacing: $tracking-tight;
}

.topbar-divider {
  width: 1px;
  height: 20px;
  background: $color-border-default;
}

.topbar-btn {
  width: 32px;
  height: 32px;
  border-radius: $radius-md;
  border: 1px solid transparent;
  background: transparent;
  color: $color-text-secondary;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: $transition-fast;

  &:hover {
    background: $color-bg-subtle;
    border-color: $color-border-default;
    color: $color-text-primary;
  }
}

.content {
  flex: 1;
  padding: $layout-content-padding;
  overflow-y: auto;
  background: $color-bg-base;
}
</style>
