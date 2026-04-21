import {
  createRouter,
  createWebHistory,
  type RouteRecordRaw,
} from 'vue-router'

import { appPages } from '@/config/appPages'
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
      ...appPages
        .filter((page) => !['restock/current', 'restock/history'].includes(page.path))
        .map((page) => ({
        path: page.path,
        name: page.name,
        component: page.component,
        meta: {
          title: page.title,
          section: page.section,
          permission: page.permission,
        },
      })),
      {
        path: 'restock/current',
        name: 'suggestion-list',
        component: () => import('@/views/SuggestionListView.vue'),
        meta: { title: '采补发起', section: 'RESTOCK', permission: 'restock:view' },
        redirect: '/restock/current/procurement',
        children: [
          {
            path: 'procurement',
            name: 'suggestion-list-procurement',
            component: () => import('@/views/suggestion/ProcurementListView.vue'),
            meta: { title: '采购建议', section: 'RESTOCK', permission: 'restock:view' },
          },
          {
            path: 'restock',
            name: 'suggestion-list-restock',
            component: () => import('@/views/suggestion/RestockListView.vue'),
            meta: { title: '补货建议', section: 'RESTOCK', permission: 'restock:view' },
          },
        ],
      },
      { path: 'restock/run', redirect: '/restock/current' },
      {
        path: 'restock/suggestions/:id',
        name: 'suggestion-detail',
        component: () => import('@/views/SuggestionDetailView.vue'),
        redirect: (to) => `/restock/suggestions/${to.params.id}/procurement`,
        children: [
          {
            path: 'procurement',
            name: 'suggestion-detail-procurement',
            component: () => import('@/views/suggestion/ProcurementDetailView.vue'),
            meta: { title: '采购建议详情', section: 'RESTOCK', permission: 'restock:view' },
          },
          {
            path: 'restock',
            name: 'suggestion-detail-restock',
            component: () => import('@/views/suggestion/RestockDetailView.vue'),
            meta: { title: '补货建议详情', section: 'RESTOCK', permission: 'restock:view' },
          },
        ],
        meta: { title: '建议详情', section: 'RESTOCK', permission: 'restock:view' },
      },
      {
        path: 'restock/history',
        name: 'history',
        component: () => import('@/views/HistoryView.vue'),
        meta: { title: '历史记录', section: 'RESTOCK', permission: 'history:view' },
        redirect: '/restock/history/procurement',
        children: [
          {
            path: 'procurement',
            name: 'history-procurement',
            component: () => import('@/views/history/ProcurementHistoryView.vue'),
            meta: { title: '采购历史', section: 'RESTOCK', permission: 'history:view' },
          },
          {
            path: 'restock',
            name: 'history-restock',
            component: () => import('@/views/history/RestockHistoryView.vue'),
            meta: { title: '补货历史', section: 'RESTOCK', permission: 'history:view' },
          },
        ],
      },
      { path: 'settings/sku', redirect: '/data/products' },
      { path: 'settings/warehouse', redirect: '/data/warehouses' },
      { path: 'settings/shop', redirect: '/data/shops' },

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

  if (to.meta.public) return true

  if (!auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (!auth.user) {
    try {
      await auth.restoreAuth()
    } catch {
      auth.clearAuth()
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }

  const requiredPermission = to.meta.permission
  if (requiredPermission && !auth.hasPermission(requiredPermission)) {
    return { path: '/403' }
  }

  return true
})

export default router
