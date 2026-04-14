export interface SyncActionDefinition {
  key: string
  jobName: string
  label: string
  url: string
}

export interface AutoSyncDefinition {
  jobName: string
  label: string
  cadence: string
}

export const ORDER_DETAIL_REFETCH_JOB_NAME = 'refetch_order_detail'
export const ORDER_DETAIL_REFETCH_LABEL = '详情获取'

export const manualSyncActions: SyncActionDefinition[] = [
  {
    key: 'sync_all',
    jobName: 'sync_all',
    label: '全量同步',
    url: '/api/sync/all',
  },
  {
    key: 'sync_shop',
    jobName: 'sync_shop',
    label: '店铺同步',
    url: '/api/sync/shop',
  },
  {
    key: 'sync_warehouse',
    jobName: 'sync_warehouse',
    label: '仓库同步',
    url: '/api/sync/warehouse',
  },
  {
    key: 'sync_product_listing',
    jobName: 'sync_product_listing',
    label: '商品同步',
    url: '/api/sync/product-listing',
  },
  {
    key: 'sync_inventory',
    jobName: 'sync_inventory',
    label: '库存同步',
    url: '/api/sync/inventory',
  },
  {
    key: 'sync_order_list',
    jobName: 'sync_order_list',
    label: '订单同步',
    url: '/api/sync/orders',
  },
  {
    key: 'sync_out_records',
    jobName: 'sync_out_records',
    label: '出库记录同步',
    url: '/api/sync/out-records',
  },
  {
    key: 'backfill_out_record_target_country',
    jobName: 'backfill_out_record_target_country',
    label: '回填出库目标国家',
    url: '/api/sync/out-records/backfill-target-country',
  },
]

export const replenishmentAction = {
  key: 'engine_run',
  label: '生成补货建议',
  url: '/api/engine/run',
}

export const autoSyncDefinitions: AutoSyncDefinition[] = [
  {
    jobName: 'sync_shop',
    label: '店铺基础同步',
    cadence: '建议每天执行 1 次，或授权状态变更后立即执行。',
  },
  {
    jobName: 'sync_warehouse',
    label: '仓库基础同步',
    cadence: '建议每天执行 1 次，或仓库配置调整后执行。',
  },
  {
    jobName: 'sync_product_listing',
    label: '商品基础同步',
    cadence: '建议每 1-2 小时执行 1 次。',
  },
  {
    jobName: 'sync_inventory',
    label: '库存同步',
    cadence: '建议每 30-60 分钟执行 1 次。',
  },
  {
    jobName: 'sync_order_list',
    label: '订单列表同步',
    cadence: '建议每 30-60 分钟执行 1 次。',
  },
  {
    jobName: 'sync_order_detail',
    label: '订单详情同步',
    cadence: '建议紧跟订单列表同步后执行。',
  },
  {
    jobName: 'sync_out_records',
    label: '出库记录同步',
    cadence: '建议每 2-4 小时执行 1 次。',
  },
]

export const syncJobLabelMap = Object.fromEntries(
  [
    ...manualSyncActions.map((item) => [item.jobName, item.label]),
    ...autoSyncDefinitions.map((item) => [item.jobName, item.label]),
    [ORDER_DETAIL_REFETCH_JOB_NAME, ORDER_DETAIL_REFETCH_LABEL],
    ['calc_engine', replenishmentAction.label],
    ['daily_archive', '每日归档'],
  ] as const,
)
