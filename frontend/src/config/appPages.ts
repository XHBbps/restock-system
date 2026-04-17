import type { Component } from 'vue'
import type { RouteRecordRaw } from 'vue-router'
import {
  ArrowDownUp,
  Boxes,
  Database,
  FileText,
  Gauge,
  History,
  LayoutDashboard,
  MapPin,
  Monitor,
  PackageOpen,
  PackageSearch,
  Plug,
  RefreshCw,
  Rocket,
  Shield,
  ShoppingCart,
  SlidersHorizontal,
  Store,
  TrendingUp,
  UserCog,
  Users,
  Warehouse,
  Wrench,
} from 'lucide-vue-next'

export type AppPageSection = 'HOME' | 'RESTOCK' | 'DATA' | 'SETTINGS'
export type AppPageNavCategory =
  | 'data-base'
  | 'data-biz'
  | 'settings-sync'
  | 'settings-config'
  | 'settings-monitor'
  | 'settings-auth'

export interface AppPageDefinition {
  name: string
  path: string
  title: string
  section: AppPageSection
  permission: string
  icon: Component
  component: NonNullable<RouteRecordRaw['component']>
  navCategory?: AppPageNavCategory
}

export interface NavCategoryMeta {
  group: AppPageSection
  label: string
  icon: Component
  permission: string
}

export const navCategoryMeta: Record<AppPageNavCategory, NavCategoryMeta> = {
  'data-base': {
    group: 'DATA',
    label: '基础数据',
    icon: Database,
    permission: 'data_base:view',
  },
  'data-biz': {
    group: 'DATA',
    label: '业务数据',
    icon: TrendingUp,
    permission: 'data_biz:view',
  },
  'settings-sync': {
    group: 'SETTINGS',
    label: '同步管理',
    icon: RefreshCw,
    permission: 'sync:view',
  },
  'settings-config': {
    group: 'SETTINGS',
    label: '基础配置',
    icon: Wrench,
    permission: 'config:view',
  },
  'settings-monitor': {
    group: 'SETTINGS',
    label: '系统监控',
    icon: Monitor,
    permission: 'monitor:view',
  },
  'settings-auth': {
    group: 'SETTINGS',
    label: '权限设置',
    icon: Shield,
    permission: 'auth:view',
  },
}

export const appPages: AppPageDefinition[] = [
  {
    name: 'workspace',
    path: 'workspace',
    title: '信息总览',
    section: 'HOME',
    permission: 'home:view',
    icon: LayoutDashboard,
    component: () => import('@/views/WorkspaceView.vue'),
  },
  {
    name: 'suggestion-list',
    path: 'restock/current',
    title: '补货发起',
    section: 'RESTOCK',
    permission: 'restock:view',
    icon: Rocket,
    component: () => import('@/views/SuggestionListView.vue'),
  },
  {
    name: 'history',
    path: 'restock/history',
    title: '历史记录',
    section: 'RESTOCK',
    permission: 'history:view',
    icon: History,
    component: () => import('@/views/HistoryView.vue'),
  },
  {
    name: 'data-shops',
    path: 'data/shops',
    title: '店铺',
    section: 'DATA',
    permission: 'data_base:view',
    icon: Store,
    navCategory: 'data-base',
    component: () => import('@/views/data/DataShopsView.vue'),
  },
  {
    name: 'data-warehouses',
    path: 'data/warehouses',
    title: '仓库',
    section: 'DATA',
    permission: 'data_base:view',
    icon: Warehouse,
    navCategory: 'data-base',
    component: () => import('@/views/data/DataWarehousesView.vue'),
  },
  {
    name: 'data-products',
    path: 'data/products',
    title: '商品',
    section: 'DATA',
    permission: 'data_base:view',
    icon: PackageSearch,
    navCategory: 'data-base',
    component: () => import('@/views/data/DataProductsView.vue'),
  },
  {
    name: 'data-orders',
    path: 'data/orders',
    title: '订单',
    section: 'DATA',
    permission: 'data_biz:view',
    icon: ShoppingCart,
    navCategory: 'data-biz',
    component: () => import('@/views/data/DataOrdersView.vue'),
  },
  {
    name: 'data-inventory',
    path: 'data/inventory',
    title: '库存',
    section: 'DATA',
    permission: 'data_biz:view',
    icon: Boxes,
    navCategory: 'data-biz',
    component: () => import('@/views/data/DataInventoryView.vue'),
  },
  {
    name: 'data-out-records',
    path: 'data/out-records',
    title: '出库',
    section: 'DATA',
    permission: 'data_biz:view',
    icon: PackageOpen,
    navCategory: 'data-biz',
    component: () => import('@/views/data/DataOutRecordsView.vue'),
  },
  {
    name: 'sync-console',
    path: 'settings/sync',
    title: '数据同步',
    section: 'SETTINGS',
    permission: 'sync:view',
    icon: ArrowDownUp,
    navCategory: 'settings-sync',
    component: () => import('@/views/SyncConsoleView.vue'),
  },
  {
    name: 'sync-log',
    path: 'settings/sync-log',
    title: '同步日志',
    section: 'SETTINGS',
    permission: 'sync:view',
    icon: FileText,
    navCategory: 'settings-sync',
    component: () => import('@/views/SyncLogView.vue'),
  },
  {
    name: 'global-config',
    path: 'settings/global',
    title: '全局参数',
    section: 'SETTINGS',
    permission: 'config:view',
    icon: SlidersHorizontal,
    navCategory: 'settings-config',
    component: () => import('@/views/GlobalConfigView.vue'),
  },
  {
    name: 'zipcode-rule',
    path: 'settings/zipcode',
    title: '邮编规则',
    section: 'SETTINGS',
    permission: 'config:view',
    icon: MapPin,
    navCategory: 'settings-config',
    component: () => import('@/views/ZipcodeRuleView.vue'),
  },
  {
    name: 'api-monitor',
    path: 'settings/api-monitor',
    title: '接口监控',
    section: 'SETTINGS',
    permission: 'monitor:view',
    icon: Plug,
    navCategory: 'settings-monitor',
    component: () => import('@/views/ApiMonitorView.vue'),
  },
  {
    name: 'performance-monitor',
    path: 'settings/performance',
    title: '性能监控',
    section: 'SETTINGS',
    permission: 'monitor:view',
    icon: Gauge,
    navCategory: 'settings-monitor',
    component: () => import('@/views/PerformanceMonitorView.vue'),
  },
  {
    name: 'auth-roles',
    path: 'settings/auth/roles',
    title: '角色配置',
    section: 'SETTINGS',
    permission: 'auth:view',
    icon: UserCog,
    navCategory: 'settings-auth',
    component: () => import('@/views/RoleConfigView.vue'),
  },
  {
    name: 'auth-users',
    path: 'settings/auth/users',
    title: '授权配置',
    section: 'SETTINGS',
    permission: 'auth:view',
    icon: Users,
    navCategory: 'settings-auth',
    component: () => import('@/views/UserConfigView.vue'),
  },
]
