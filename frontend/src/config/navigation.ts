import type { Component } from 'vue'
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

export interface NavItem {
  to: string
  label: string
  icon: Component
  permission?: string
}

export interface NavSubCategory {
  label: string
  icon: Component
  permission?: string
  items: NavItem[]
}

export interface NavGroup {
  title: string
  children: (NavItem | NavSubCategory)[]
}

export function isSubCategory(child: NavItem | NavSubCategory): child is NavSubCategory {
  return 'items' in child
}

export const navigationGroups: NavGroup[] = [
  {
    title: 'HOME',
    children: [
      { to: '/workspace', label: '信息总览', icon: LayoutDashboard, permission: 'home:view' },
    ],
  },
  {
    title: 'RESTOCK',
    children: [
      { to: '/restock/current', label: '补货发起', icon: Rocket, permission: 'restock:view' },
      { to: '/restock/history', label: '历史记录', icon: History, permission: 'history:view' },
    ],
  },
  {
    title: 'DATA',
    children: [
      {
        label: '基础数据',
        icon: Database,
        permission: 'data_base:view',
        items: [
          { to: '/data/shops', label: '店铺', icon: Store, permission: 'data_base:view' },
          { to: '/data/warehouses', label: '仓库', icon: Warehouse, permission: 'data_base:view' },
          { to: '/data/products', label: '商品', icon: PackageSearch, permission: 'data_base:view' },
        ],
      },
      {
        label: '业务数据',
        icon: TrendingUp,
        permission: 'data_biz:view',
        items: [
          { to: '/data/orders', label: '订单', icon: ShoppingCart, permission: 'data_biz:view' },
          { to: '/data/inventory', label: '库存', icon: Boxes, permission: 'data_biz:view' },
          { to: '/data/out-records', label: '出库', icon: PackageOpen, permission: 'data_biz:view' },
        ],
      },
    ],
  },
  {
    title: 'SETTINGS',
    children: [
      {
        label: '同步管理',
        icon: RefreshCw,
        permission: 'sync:view',
        items: [
          { to: '/settings/sync', label: '数据同步', icon: ArrowDownUp, permission: 'sync:view' },
          { to: '/settings/sync-log', label: '同步日志', icon: FileText, permission: 'sync:view' },
        ],
      },
      {
        label: '基础配置',
        icon: Wrench,
        permission: 'config:view',
        items: [
          { to: '/settings/global', label: '全局参数', icon: SlidersHorizontal, permission: 'config:view' },
          { to: '/settings/zipcode', label: '邮编规则', icon: MapPin, permission: 'config:view' },
        ],
      },
      {
        label: '系统监控',
        icon: Monitor,
        permission: 'monitor:view',
        items: [
          { to: '/settings/api-monitor', label: '接口监控', icon: Plug, permission: 'monitor:view' },
          { to: '/settings/performance', label: '性能监控', icon: Gauge, permission: 'monitor:view' },
        ],
      },
      {
        label: '权限设置',
        icon: Shield,
        permission: 'auth:view',
        items: [
          { to: '/settings/auth/roles', label: '角色配置', icon: UserCog, permission: 'auth:view' },
          { to: '/settings/auth/users', label: '授权配置', icon: Users, permission: 'auth:view' },
        ],
      },
    ],
  },
]
