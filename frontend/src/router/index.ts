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
      {
        path: 'workspace',
        name: 'workspace',
        component: () => import('@/views/WorkspaceView.vue'),
        meta: { title: '总览', section: '工作台' },
      },
      {
        path: 'sync',
        name: 'sync-console',
        component: () => import('@/views/SyncConsoleView.vue'),
        meta: { title: '数据同步', section: '数据同步中心' },
      },
      { path: 'sync/manual', redirect: '/sync' },
      { path: 'sync/auto', redirect: '/sync' },
      { path: 'sync/overview', redirect: '/sync' },
      {
        path: 'replenishment/run',
        name: 'replenishment-run',
        component: () => import('@/views/ReplenishmentRunView.vue'),
        meta: { title: '补货触发', section: '补货中心' },
      },
      {
        path: 'replenishment/current',
        name: 'suggestion-list',
        component: () => import('@/views/SuggestionListView.vue'),
        meta: { title: '当前建议', section: '补货中心' },
      },
      {
        path: 'replenishment/history',
        name: 'history',
        component: () => import('@/views/HistoryView.vue'),
        meta: { title: '历史记录', section: '补货中心' },
      },
      {
        path: 'replenishment/suggestions/:id',
        name: 'suggestion-detail',
        component: () => import('@/views/SuggestionDetailView.vue'),
        meta: { title: '建议详情', section: '补货中心' },
      },
      {
        path: 'data/orders',
        name: 'data-orders',
        component: () => import('@/views/data/DataOrdersView.vue'),
        meta: { title: '订单数据', section: '数据查看' },
      },
      {
        path: 'data/inventory',
        name: 'data-inventory',
        component: () => import('@/views/data/DataInventoryView.vue'),
        meta: { title: '库存数据', section: '数据查看' },
      },
      {
        path: 'data/out-records',
        name: 'data-out-records',
        component: () => import('@/views/data/DataOutRecordsView.vue'),
        meta: { title: '出库记录', section: '数据查看' },
      },
      {
        path: 'data/warehouses',
        name: 'data-warehouses',
        component: () => import('@/views/data/DataWarehousesView.vue'),
        meta: { title: '仓库数据', section: '数据查看' },
      },
      {
        path: 'data/shops',
        name: 'data-shops',
        component: () => import('@/views/data/DataShopsView.vue'),
        meta: { title: '店铺数据', section: '数据查看' },
      },
      {
        path: 'data/products',
        name: 'data-products',
        component: () => import('@/views/data/DataProductsView.vue'),
        meta: { title: '商品数据', section: '数据查看' },
      },
      {
        path: 'config/sku',
        name: 'sku-config',
        component: () => import('@/views/SkuConfigView.vue'),
        meta: { title: 'SKU 配置', section: '基础配置' },
      },
      {
        path: 'config/global',
        name: 'global-config',
        component: () => import('@/views/GlobalConfigView.vue'),
        meta: { title: '全局参数', section: '基础配置' },
      },
      {
        path: 'config/warehouse',
        name: 'warehouse',
        component: () => import('@/views/WarehouseView.vue'),
        meta: { title: '仓库配置', section: '基础配置' },
      },
      {
        path: 'config/zipcode',
        name: 'zipcode-rule',
        component: () => import('@/views/ZipcodeRuleView.vue'),
        meta: { title: '邮编规则', section: '基础配置' },
      },
      {
        path: 'config/shop',
        name: 'shop',
        component: () => import('@/views/ShopView.vue'),
        meta: { title: '店铺管理', section: '基础配置' },
      },
      {
        path: 'troubleshooting/api-monitor',
        name: 'api-monitor',
        component: () => import('@/views/ApiMonitorView.vue'),
        meta: { title: '接口监控', section: '监控与排查' },
      },
      {
        path: 'troubleshooting/performance',
        name: 'performance-monitor',
        component: () => import('@/views/PerformanceMonitorView.vue'),
        meta: { title: '性能监控', section: '监控与排查' },
      },
      {
        path: 'troubleshooting/overstock',
        name: 'overstock',
        component: () => import('@/views/OverstockView.vue'),
        meta: { title: '积压提示', section: '监控与排查' },
      },
      { path: 'suggestions', redirect: '/replenishment/current' },
      { path: 'suggestions/:id', redirect: (to) => `/replenishment/suggestions/${to.params.id}` },
      { path: 'history', redirect: '/replenishment/history' },
      { path: 'ops/sync', redirect: '/sync' },
      { path: 'monitor/overstock', redirect: '/troubleshooting/overstock' },
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
