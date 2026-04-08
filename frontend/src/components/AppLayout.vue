<template>
  <div class="app-layout">
    <!-- 左侧侧栏 -->
    <aside class="sidebar">
      <div class="sidebar-logo">
        <span class="logo-mark">⊜</span>
        <span class="logo-text">Restock</span>
      </div>

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
            <span class="nav-item-icon">{{ item.icon }}</span>
            <span class="nav-item-label">{{ item.label }}</span>
          </RouterLink>
        </div>
      </nav>

      <div class="sidebar-footer">
        <el-button text class="logout-btn" @click="handleLogout">登出</el-button>
      </div>
    </aside>

    <!-- 顶部条 + 内容 -->
    <main class="main">
      <header class="topbar">
        <h2 class="topbar-title">{{ currentTitle }}</h2>
        <div class="topbar-right">
          <span class="topbar-user">采购员</span>
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
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const currentTitle = computed(() => (route.meta.title as string) || '')

const menuGroups = [
  {
    title: '补货建议',
    items: [
      { to: '/suggestions', icon: '📋', label: '当前建议单' },
      { to: '/history', icon: '🕒', label: '历史记录' }
    ]
  },
  {
    title: '配置',
    items: [
      { to: '/config/sku', icon: '⚙', label: 'SKU 配置' },
      { to: '/config/global', icon: '⚙', label: '全局参数' },
      { to: '/config/warehouse', icon: '🏬', label: '仓库与国家' },
      { to: '/config/zipcode', icon: '✉', label: '邮编规则' },
      { to: '/config/shop', icon: '🏪', label: '店铺管理' }
    ]
  },
  {
    title: '观测',
    items: [
      { to: '/monitor/overstock', icon: '📦', label: '积压提示' },
      { to: '/monitor/api', icon: '📊', label: '接口监控' }
    ]
  },
  {
    title: '操作',
    items: [{ to: '/tasks/manual', icon: '🔧', label: '手动同步/计算' }]
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
}

.sidebar {
  width: $layout-sidebar-width;
  flex-shrink: 0;
  background: $color-bg-card;
  border-right: 1px solid $color-border-subtle;
  display: flex;
  flex-direction: column;
  padding: $space-6 $space-4;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: $space-3;
  padding: $space-2 $space-3;
  margin-bottom: $space-8;

  .logo-mark {
    color: $color-brand-primary;
    font-size: $font-size-2xl;
  }
  .logo-text {
    font-size: $font-size-lg;
    font-weight: $font-weight-semibold;
    color: $color-text-primary;
  }
}

.nav {
  flex: 1;
  overflow-y: auto;
}

.nav-group + .nav-group {
  margin-top: $space-6;
}

.nav-group-title {
  font-size: $font-size-xs;
  color: $color-text-secondary;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0 $space-3 $space-2;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: $space-3;
  padding: $space-3 $space-3;
  margin-bottom: $space-1;
  border-radius: $radius-md;
  color: $color-text-primary;
  text-decoration: none;
  font-size: $font-size-md;
  transition: $transition-base;

  &:hover {
    background: $color-brand-primary-soft;
  }
}

.nav-item-active {
  background: $color-brand-primary !important;
  color: $color-text-on-brand !important;
}

.nav-item-icon {
  width: 20px;
  text-align: center;
}

.sidebar-footer {
  padding-top: $space-4;
  border-top: 1px solid $color-border-subtle;
}

.logout-btn {
  width: 100%;
  color: $color-text-secondary;
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  height: $layout-topbar-height;
  background: $color-bg-card;
  border-bottom: 1px solid $color-border-subtle;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 $space-8;
}

.topbar-title {
  margin: 0;
  font-size: $font-size-xl;
  font-weight: $font-weight-semibold;
  color: $color-text-primary;
}

.topbar-user {
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.content {
  flex: 1;
  padding: $layout-content-padding;
  overflow-y: auto;
}
</style>
