import type { Component } from 'vue'
import {
  Activity,
  Boxes,
  ClipboardList,
  Database,
  FileText,
  Gauge,
  History,
  LayoutDashboard,
  PackageSearch,
  PlayCircle,
  RefreshCw,
  Settings,
  ShieldAlert,
  Store,
  TrendingUp,
  Truck,
  Warehouse,
} from 'lucide-vue-next'

export interface NavItem {
  to: string
  label: string
  icon: Component
}

export interface NavSubCategory {
  label: string
  icon: Component
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
      { to: '/workspace', label: '总览', icon: LayoutDashboard },
    ],
  },
  {
    title: 'RESTOCK',
    children: [
      { to: '/restock/current', label: '当前建议', icon: ClipboardList },
      { to: '/restock/run', label: '发起补货', icon: PlayCircle },
      { to: '/restock/history', label: '历史记录', icon: History },
    ],
  },
  {
    title: 'DATA',
    children: [
      {
        label: '基础数据',
        icon: Database,
        items: [
          { to: '/data/shops', label: '店铺', icon: Store },
          { to: '/data/warehouses', label: '仓库', icon: Warehouse },
          { to: '/data/products', label: '商品', icon: PackageSearch },
        ],
      },
      {
        label: '业务数据',
        icon: TrendingUp,
        items: [
          { to: '/data/orders', label: '订单', icon: ClipboardList },
          { to: '/data/inventory', label: '库存', icon: Boxes },
          { to: '/data/out-records', label: '出库记录', icon: Truck },
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
        items: [
          { to: '/settings/sync', label: '数据同步', icon: RefreshCw },
          { to: '/settings/sync-log', label: '同步日志', icon: FileText },
        ],
      },
      {
        label: '基础配置',
        icon: Settings,
        items: [
          { to: '/settings/global', label: '全局参数', icon: Settings },
          { to: '/settings/zipcode', label: '邮编规则', icon: Truck },
        ],
      },
      {
        label: '系统监控',
        icon: ShieldAlert,
        items: [
          { to: '/settings/api-monitor', label: '接口监控', icon: ShieldAlert },
          { to: '/settings/performance', label: '性能监控', icon: Gauge },
          { to: '/settings/overstock', label: '积压提示', icon: Activity },
        ],
      },
    ],
  },
]
