// 路由表 + 鉴权守卫
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    component: () => import('@/components/AppLayout.vue'),
    redirect: '/suggestions',
    children: [
      // Replenish
      {
        path: 'suggestions',
        name: 'suggestion-list',
        component: () => import('@/views/SuggestionListView.vue'),
        meta: { title: '补货建议' }
      },
      {
        path: 'suggestions/:id',
        name: 'suggestion-detail',
        component: () => import('@/views/SuggestionDetailView.vue'),
        meta: { title: '建议详情' }
      },
      {
        path: 'history',
        name: 'history',
        component: () => import('@/views/HistoryView.vue'),
        meta: { title: '历史记录' }
      },
      // External data
      {
        path: 'data/orders',
        name: 'data-orders',
        component: () => import('@/views/data/DataOrdersView.vue'),
        meta: { title: '订单列表' }
      },
      {
        path: 'data/inventory',
        name: 'data-inventory',
        component: () => import('@/views/data/DataInventoryView.vue'),
        meta: { title: '库存明细' }
      },
      {
        path: 'data/out-records',
        name: 'data-out-records',
        component: () => import('@/views/data/DataOutRecordsView.vue'),
        meta: { title: '其他出库列表' }
      },
      {
        path: 'data/warehouses',
        name: 'data-warehouses',
        component: () => import('@/views/data/DataWarehousesView.vue'),
        meta: { title: '仓库列表' }
      },
      {
        path: 'data/shops',
        name: 'data-shops',
        component: () => import('@/views/data/DataShopsView.vue'),
        meta: { title: '店铺列表' }
      },
      {
        path: 'data/products',
        name: 'data-products',
        component: () => import('@/views/data/DataProductsView.vue'),
        meta: { title: '在线产品信息' }
      },
      // Config
      {
        path: 'config/sku',
        name: 'sku-config',
        component: () => import('@/views/SkuConfigView.vue'),
        meta: { title: 'SKU 配置' }
      },
      {
        path: 'config/global',
        name: 'global-config',
        component: () => import('@/views/GlobalConfigView.vue'),
        meta: { title: '全局参数' }
      },
      {
        path: 'config/warehouse',
        name: 'warehouse',
        component: () => import('@/views/WarehouseView.vue'),
        meta: { title: '仓库与国家' }
      },
      {
        path: 'config/zipcode',
        name: 'zipcode-rule',
        component: () => import('@/views/ZipcodeRuleView.vue'),
        meta: { title: '邮编规则' }
      },
      {
        path: 'config/shop',
        name: 'shop',
        component: () => import('@/views/ShopView.vue'),
        meta: { title: '店铺管理' }
      },
      // Observability
      {
        path: 'monitor/overstock',
        name: 'overstock',
        component: () => import('@/views/OverstockView.vue'),
        meta: { title: '积压提示' }
      },
      // Operations (merged 同步管理)
      {
        path: 'ops/sync',
        name: 'sync-management',
        component: () => import('@/views/SyncManagementView.vue'),
        meta: { title: '同步管理' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
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
