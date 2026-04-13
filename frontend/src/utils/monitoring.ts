import type { TaskStatus } from '@/api/task'

export interface MonitorDisplayMeta {
  label: string
  raw: string
}

const SAIHU_ENDPOINT_LABELS: Record<string, string> = {
  '/api/order/api/product/pageList.json': '商品列表同步',
  '/api/warehouseManage/warehouseList.json': '仓库列表同步',
  '/api/warehouseManage/warehouseItemList.json': '库存同步',
  '/api/warehouseInOut/outRecords.json': '出库记录同步',
  '/api/order/pageList.json': '订单列表同步',
  '/api/order/detailByOrderId.json': '订单详情同步',
  '/api/shop/pageList.json': '店铺同步',
}

const INTERNAL_API_PREFIX_LABELS: Array<{ prefix: string; label: string }> = [
  { prefix: '/api/monitor/api-calls/recent', label: '最近接口调用查询' },
  { prefix: '/api/monitor/api-calls/', label: '接口调用重试' },
  { prefix: '/api/monitor/api-calls', label: '接口监控聚合查询' },
  { prefix: '/api/tasks/', label: '任务进度查询' },
  { prefix: '/api/sync/', label: '同步控制接口' },
  { prefix: '/api/data/', label: '基础数据查询接口' },
  { prefix: '/api/suggestions/', label: '补货建议接口' },
  { prefix: '/api/config/', label: '系统配置接口' },
  { prefix: '/api/auth/', label: '认证接口' },
]

const RESOURCE_EXTENSION_LABELS: Array<{ pattern: RegExp; label: string }> = [
  { pattern: /\.(js|mjs|ts|tsx)$/i, label: '脚本资源' },
  { pattern: /\.css$/i, label: '样式资源' },
  { pattern: /\.(png|jpg|jpeg|gif|svg|webp|ico|bmp)$/i, label: '图片资源' },
  { pattern: /\.(woff2?|ttf|otf|eot)$/i, label: '字体资源' },
  { pattern: /\.map$/i, label: '源码映射' },
]

export function getPercentileIndex(length: number, percentile: number): number {
  if (length <= 0) return 0
  return Math.max(0, Math.ceil(length * percentile) - 1)
}

export function normalizeMonitorResourceName(name: string): string {
  if (!name) return ''

  try {
    const url = new URL(name, 'http://localhost')
    if (url.protocol === 'http:' || url.protocol === 'https:') {
      return `${url.pathname}${url.search}` || name
    }
  } catch {
    // Fall through to raw value.
  }

  return name
}

export function formatMonitorEndpoint(endpoint: string): MonitorDisplayMeta {
  const raw = normalizeMonitorResourceName(endpoint) || endpoint
  const path = stripQueryAndHash(raw)
  const label = SAIHU_ENDPOINT_LABELS[path] || `赛狐接口：${formatPathFallback(path)}`

  return { label, raw }
}

export function formatPerformanceResourceName(
  name: string,
  initiatorType?: string | null,
): MonitorDisplayMeta {
  const raw = normalizeMonitorResourceName(name) || name
  const path = stripQueryAndHash(raw)
  const normalizedType = (initiatorType || '').toLowerCase()

  if (normalizedType === 'navigation') {
    return {
      label: `页面导航：${path || '/'}`,
      raw,
    }
  }

  const internalApiLabel = INTERNAL_API_PREFIX_LABELS.find((item) => path.startsWith(item.prefix))?.label
  if (internalApiLabel) {
    return { label: internalApiLabel, raw }
  }

  if (path === '/' || path.endsWith('.html')) {
    return {
      label: `页面导航：${path || '/'}`,
      raw,
    }
  }

  const viteLabel = formatViteResourceLabel(path)
  if (viteLabel) {
    return { label: viteLabel, raw }
  }

  const resourceLabel = RESOURCE_EXTENSION_LABELS.find((item) => item.pattern.test(path))?.label
  if (resourceLabel) {
    return { label: `${resourceLabel}：${getFileLabel(path)}`, raw }
  }

  if (path.startsWith('/api/')) {
    return { label: `系统接口：${formatPathFallback(path)}`, raw }
  }

  return {
    label: `资源文件：${getFileLabel(path)}`,
    raw,
  }
}

export function getTaskTerminalFeedback(status: TaskStatus): {
  type: 'success' | 'warning' | 'error'
  message: string
} {
  switch (status) {
    case 'success':
      return { type: 'success', message: '重试任务已成功完成，监控数据已刷新' }
    case 'failed':
      return { type: 'error', message: '重试任务执行失败，监控数据已刷新' }
    case 'skipped':
      return { type: 'warning', message: '重试任务已跳过，监控数据已刷新' }
    case 'cancelled':
      return { type: 'warning', message: '重试任务已取消，监控数据已刷新' }
    default:
      return { type: 'warning', message: '重试任务已结束，监控数据已刷新' }
  }
}

function stripQueryAndHash(value: string): string {
  return value.split('#', 1)[0].split('?', 1)[0] || value
}

function formatPathFallback(path: string): string {
  const cleaned = stripExtension(getFileLabel(path))
  return cleaned || path || '未知接口'
}

function getFileLabel(path: string): string {
  const cleaned = stripQueryAndHash(path).replace(/\/+$/, '')
  if (!cleaned || cleaned === '/') return '/'

  const parts = cleaned.split('/').filter(Boolean)
  return parts[parts.length - 1] || cleaned
}

function stripExtension(value: string): string {
  return value.replace(/\.[^.]+$/, '')
}

function formatViteResourceLabel(path: string): string | null {
  if (path.startsWith('/@vite/')) {
    return `Vite 开发资源：${getFileLabel(path)}`
  }
  if (path.startsWith('/src/')) {
    return `本地源码资源：${getFileLabel(path)}`
  }
  if (path.startsWith('/assets/')) {
    return `构建产物资源：${getFileLabel(path)}`
  }
  return null
}
