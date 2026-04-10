import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

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
      // --- HOME ---
      {
        path: 'workspace',
        name: 'workspace',
        component: () => import('@/views/WorkspaceView.vue'),
        meta: { title: '总览', section: 'HOME' },
      },

      // --- RESTOCK ---
      {
        path: 'restock/current',
        name: 'suggestion-list',
        component: () => import('@/views/SuggestionListView.vue'),
        meta: { title: '当前建议', section: 'RESTOCK' },
      },
      {
        path: 'restock/run',
        name: 'replenishment-run',
        component: () => import('@/views/ReplenishmentRunView.vue'),
        meta: { title: '发起补货', section: 'RESTOCK' },
      },
      {
        path: 'restock/history',
        name: 'history',
        component: () => import('@/views/HistoryView.vue'),
        meta: { title: '历史记录', section: 'RESTOCK' },
      },
      {
        path: 'restock/suggestions/:id',
        name: 'suggestion-detail',
        component: () => import('@/views/SuggestionDetailView.vue'),
        meta: { title: '建议详情', section: 'RESTOCK' },
      },

      // --- DATA ---
      {
        path: 'data/shops',
        name: 'data-shops',
        component: () => import('@/views/data/DataShopsView.vue'),
        meta: { title: '店铺', section: 'DATA' },
      },
      {
        path: 'data/warehouses',
        name: 'data-warehouses',
        component: () => import('@/views/data/DataWarehousesView.vue'),
        meta: { title: '仓库', section: 'DATA' },
      },
      {
        path: 'data/products',
        name: 'data-products',
        component: () => import('@/views/data/DataProductsView.vue'),
        meta: { title: '商品', section: 'DATA' },
      },
      {
        path: 'data/orders',
        name: 'data-orders',
        component: () => import('@/views/data/DataOrdersView.vue'),
        meta: { title: '订单', section: 'DATA' },
      },
      {
        path: 'data/inventory',
        name: 'data-inventory',
        component: () => import('@/views/data/DataInventoryView.vue'),
        meta: { title: '库存', section: 'DATA' },
      },
      {
        path: 'data/out-records',
        name: 'data-out-records',
        component: () => import('@/views/data/DataOutRecordsView.vue'),
        meta: { title: '出库记录', section: 'DATA' },
      },

      // --- SETTINGS ---
      {
        path: 'settings/sync',
        name: 'sync-console',
        component: () => import('@/views/SyncConsoleView.vue'),
        meta: { title: '数据同步', section: 'SETTINGS' },
      },
      {
        path: 'settings/sync-log',
        name: 'sync-log',
        component: () => import('@/views/SyncLogView.vue'),
        meta: { title: '同步日志', section: 'SETTINGS' },
      },
      {
        path: 'settings/global',
        name: 'global-config',
        component: () => import('@/views/GlobalConfigView.vue'),
        meta: { title: '全局参数', section: 'SETTINGS' },
      },
      {
        path: 'settings/sku',
        name: 'sku-config',
        component: () => import('@/views/SkuConfigView.vue'),
        meta: { title: 'SKU 配置', section: 'SETTINGS' },
      },
      {
        path: 'settings/warehouse',
        name: 'warehouse',
        component: () => import('@/views/WarehouseView.vue'),
        meta: { title: '仓库配置', section: 'SETTINGS' },
      },
      {
        path: 'settings/zipcode',
        name: 'zipcode-rule',
        component: () => import('@/views/ZipcodeRuleView.vue'),
        meta: { title: '邮编规则', section: 'SETTINGS' },
      },
      { path: 'settings/shop', redirect: '/data/shops' },
      {
        path: 'settings/api-monitor',
        name: 'api-monitor',
        component: () => import('@/views/ApiMonitorView.vue'),
        meta: { title: '接口监控', section: 'SETTINGS' },
      },
      {
        path: 'settings/performance',
        name: 'performance-monitor',
        component: () => import('@/views/PerformanceMonitorView.vue'),
        meta: { title: '性能监控', section: 'SETTINGS' },
      },
      {
        path: 'settings/overstock',
        name: 'overstock',
        component: () => import('@/views/OverstockView.vue'),
        meta: { title: '积压提示', section: 'SETTINGS' },
      },

      // --- Legacy redirects ---
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
      { path: 'troubleshooting/overstock', redirect: '/settings/overstock' },
      { path: 'ops/sync', redirect: '/settings/sync' },
      { path: 'monitor/overstock', redirect: '/settings/overstock' },

      // --- Not found ---
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

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.public) return true
  if (!auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
