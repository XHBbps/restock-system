import {
  createRouter,
  createWebHistory,
  type RouteRecordRaw,
} from 'vue-router'

import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    section?: string
    public?: boolean
    permission?: string
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/',
    component: () => import('@/components/AppLayout.vue'),
    redirect: '/workspace',
    children: [
      {
        path: 'workspace',
        name: 'workspace',
        component: () => import('@/views/WorkspaceView.vue'),
        meta: { title: '信息总览', section: 'HOME', permission: 'home:view' },
      },

      {
        path: 'restock/current',
        name: 'suggestion-list',
        component: () => import('@/views/SuggestionListView.vue'),
        meta: { title: '补货发起', section: 'RESTOCK', permission: 'restock:view' },
      },
      { path: 'restock/run', redirect: '/restock/current' },
      {
        path: 'restock/history',
        name: 'history',
        component: () => import('@/views/HistoryView.vue'),
        meta: { title: '历史记录', section: 'RESTOCK', permission: 'history:view' },
      },
      {
        path: 'restock/suggestions/:id',
        name: 'suggestion-detail',
        component: () => import('@/views/SuggestionDetailView.vue'),
        meta: { title: '建议详情', section: 'RESTOCK', permission: 'restock:view' },
      },

      {
        path: 'data/shops',
        name: 'data-shops',
        component: () => import('@/views/data/DataShopsView.vue'),
        meta: { title: '店铺', section: 'DATA', permission: 'data_base:view' },
      },
      {
        path: 'data/warehouses',
        name: 'data-warehouses',
        component: () => import('@/views/data/DataWarehousesView.vue'),
        meta: { title: '仓库', section: 'DATA', permission: 'data_base:view' },
      },
      {
        path: 'data/products',
        name: 'data-products',
        component: () => import('@/views/data/DataProductsView.vue'),
        meta: { title: '商品', section: 'DATA', permission: 'data_base:view' },
      },
      {
        path: 'data/orders',
        name: 'data-orders',
        component: () => import('@/views/data/DataOrdersView.vue'),
        meta: { title: '订单', section: 'DATA', permission: 'data_biz:view' },
      },
      {
        path: 'data/inventory',
        name: 'data-inventory',
        component: () => import('@/views/data/DataInventoryView.vue'),
        meta: { title: '库存', section: 'DATA', permission: 'data_biz:view' },
      },
      {
        path: 'data/out-records',
        name: 'data-out-records',
        component: () => import('@/views/data/DataOutRecordsView.vue'),
        meta: { title: '出库', section: 'DATA', permission: 'data_biz:view' },
      },

      {
        path: 'settings/sync',
        name: 'sync-console',
        component: () => import('@/views/SyncConsoleView.vue'),
        meta: { title: '数据同步', section: 'SETTINGS', permission: 'sync:view' },
      },
      {
        path: 'settings/sync-log',
        name: 'sync-log',
        component: () => import('@/views/SyncLogView.vue'),
        meta: { title: '同步日志', section: 'SETTINGS', permission: 'sync:view' },
      },
      {
        path: 'settings/global',
        name: 'global-config',
        component: () => import('@/views/GlobalConfigView.vue'),
        meta: { title: '全局参数', section: 'SETTINGS', permission: 'config:view' },
      },
      { path: 'settings/sku', redirect: '/data/products' },
      { path: 'settings/warehouse', redirect: '/data/warehouses' },
      {
        path: 'settings/zipcode',
        name: 'zipcode-rule',
        component: () => import('@/views/ZipcodeRuleView.vue'),
        meta: { title: '邮编规则', section: 'SETTINGS', permission: 'config:view' },
      },
      { path: 'settings/shop', redirect: '/data/shops' },
      {
        path: 'settings/api-monitor',
        name: 'api-monitor',
        component: () => import('@/views/ApiMonitorView.vue'),
        meta: { title: '接口监控', section: 'SETTINGS', permission: 'monitor:view' },
      },
      {
        path: 'settings/performance',
        name: 'performance-monitor',
        component: () => import('@/views/PerformanceMonitorView.vue'),
        meta: { title: '性能监控', section: 'SETTINGS', permission: 'monitor:view' },
      },
      {
        path: 'settings/auth/roles',
        name: 'auth-roles',
        component: () => import('@/views/RoleConfigView.vue'),
        meta: { title: '角色配置', section: 'SETTINGS', permission: 'auth:view' },
      },
      {
        path: 'settings/auth/users',
        name: 'auth-users',
        component: () => import('@/views/UserConfigView.vue'),
        meta: { title: '授权配置', section: 'SETTINGS', permission: 'auth:view' },
      },

      { path: 'sync', redirect: '/settings/sync' },
      { path: 'sync/manual', redirect: '/settings/sync' },
      { path: 'sync/auto', redirect: '/settings/sync' },
      { path: 'sync/overview', redirect: '/settings/sync' },
      { path: 'replenishment/current', redirect: '/restock/current' },
      { path: 'replenishment/run', redirect: '/restock/run' },
      { path: 'replenishment/history', redirect: '/restock/history' },
      { path: 'replenishment/suggestions/:id', redirect: (to) => `/restock/suggestions/${to.params.id}` },
      { path: 'suggestions', redirect: '/restock/current' },
      { path: 'suggestions/:id', redirect: (to) => `/restock/suggestions/${to.params.id}` },
      { path: 'history', redirect: '/restock/history' },
      { path: 'config/sku', redirect: '/settings/sku' },
      { path: 'config/global', redirect: '/settings/global' },
      { path: 'config/warehouse', redirect: '/settings/warehouse' },
      { path: 'config/zipcode', redirect: '/settings/zipcode' },
      { path: 'config/shop', redirect: '/settings/shop' },
      { path: 'troubleshooting/api-monitor', redirect: '/settings/api-monitor' },
      { path: 'troubleshooting/performance', redirect: '/settings/performance' },
      { path: 'ops/sync', redirect: '/settings/sync' },

      {
        path: '403',
        name: 'not-authorized',
        component: () => import('@/views/NotAuthorizedView.vue'),
        meta: { title: '无权限' },
      },
      {
        path: ':pathMatch(.*)*',
        name: 'not-found',
        component: () => import('@/views/NotFoundView.vue'),
        meta: { title: '未找到' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  // Public routes (login page)
  if (to.meta.public) return true

  // Not authenticated → login
  if (!auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  // Restore user info if needed (page refresh: token exists but Pinia store lost)
  if (!auth.user) {
    try {
      await auth.restoreAuth()
    } catch {
      auth.clearAuth()
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }

  // Permission check
  const requiredPermission = to.meta.permission
  if (requiredPermission && !auth.hasPermission(requiredPermission)) {
    return { path: '/403' }
  }

  return true
})

export default router
