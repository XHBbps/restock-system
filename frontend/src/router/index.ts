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
      ...appPages.map((page) => ({
        path: page.path,
        name: page.name,
        component: page.component,
        meta: {
          title: page.title,
          section: page.section,
          permission: page.permission,
        },
      })),
      { path: 'restock/run', redirect: '/restock/current' },
      {
        path: 'restock/suggestions/:id',
        name: 'suggestion-detail',
        component: () => import('@/views/SuggestionDetailView.vue'),
        meta: { title: '建议详情', section: 'RESTOCK', permission: 'restock:view' },
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
