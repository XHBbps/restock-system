<template>
  <PageSectionCard title="订单列表">
    <template #actions>
      <div class="order-actions">
        <div class="order-filters">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD"
            style="width: 260px"
            @change="reloadFirstPage"
          />
          <el-input
            v-model="filters.sku"
            placeholder="SKU / 订单号"
            clearable
            style="width: 200px"
            @input="scheduleSkuReload"
            @keyup.enter="reloadFirstPage"
            @clear="reloadFirstPage"
          />
          <el-select v-model="filters.country" placeholder="国家" clearable filterable style="width: 140px" @change="reloadFirstPage">
            <el-option v-for="c in COUNTRY_OPTIONS" :key="c.code" :label="c.code" :value="c.code" />
          </el-select>
          <el-select v-model="filters.shop" placeholder="店铺" clearable filterable style="width: 160px" @change="reloadFirstPage">
            <el-option v-for="s in shopOptions" :key="s" :label="s" :value="s" />
          </el-select>
          <el-select v-model="filters.status" placeholder="状态" clearable style="width: 140px" @change="reloadFirstPage">
            <el-option label="已发货" value="Shipped" />
            <el-option label="部分发货" value="PartiallyShipped" />
            <el-option label="未发货" value="Unshipped" />
            <el-option label="待处理" value="Pending" />
            <el-option label="已取消" value="Canceled" />
          </el-select>
        </div>
        <div class="order-detail-fetch-slot">
          <OrderDetailFetchAction @started="handleDetailFetchStarted" />
        </div>
      </div>
    </template>

    <el-table v-loading="loading" :data="rows" table-layout="auto" @sort-change="handleSortChange">
      <el-table-column label="订单号" prop="amazonOrderId" min-width="240" sortable="custom">
        <template #default="{ row }">
          <span class="mono nowrap">{{ row.amazonOrderId }}</span>
        </template>
      </el-table-column>
      <el-table-column label="店铺" prop="shopId" width="96" sortable="custom">
        <template #default="{ row }">
          <span class="mono muted nowrap">{{ row.shopId }}</span>
        </template>
      </el-table-column>
      <el-table-column label="国家" prop="countryCode" width="72" align="center" sortable="custom">
        <template #default="{ row }">
          <el-tag size="small">{{ row.countryCode }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" prop="orderStatus" width="128" sortable="custom">
        <template #default="{ row }">
          <el-tag :type="statusType(row.orderStatus)" size="small">{{ statusLabel(row.orderStatus) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="金额" prop="orderTotalAmount" min-width="136" align="right" sortable="custom">
        <template #default="{ row }">
          <span v-if="row.orderTotalAmount" class="mono nowrap">{{ row.orderTotalAmount }} {{ row.orderTotalCurrency }}</span>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="明细数" prop="itemCount" width="80" align="right" sortable="custom" show-overflow-tooltip>
        <template #default="{ row }">{{ row.itemCount }}</template>
      </el-table-column>
      <el-table-column label="详情状态" prop="hasDetail" width="120" align="center" sortable="custom">
        <template #default="{ row }">
          <el-tag v-if="row.hasDetail" type="success" size="small">已拉取</el-tag>
          <el-tag v-else type="info" size="small">无详情</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="下单时间" prop="purchaseDate" min-width="168" sortable="custom">
        <template #default="{ row }">
          <span class="muted mono nowrap">{{ formatDateTime(row.purchaseDate) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="84" align="center">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <TablePaginationBar
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100, 200]"
      @current-change="handlePageChange"
      @size-change="handlePageSizeChange"
    />

    <TaskProgress v-if="detailFetchTaskId" :task-id="detailFetchTaskId" @terminal="onDetailFetchDone" />

    <el-dialog v-model="dialogVisible" :title="detail ? `订单详情 · ${detail.amazonOrderId}` : '加载中...'" width="800px">
      <div v-if="detail" class="detail-body">
        <div class="detail-section">
          <div class="section-title">基本信息</div>
          <div class="kv-grid">
            <div><span class="label">店铺 ID（shopId）</span><span class="mono">{{ detail.shopId }}</span></div>
            <div><span class="label">站点 ID（marketplaceId）</span><span class="mono">{{ detail.marketplaceId }}</span></div>
            <div><span class="label">国家代码（countryCode）</span><span class="mono">{{ detail.countryCode }}</span></div>
            <div><span class="label">订单状态（orderStatus）</span><span class="mono">{{ detail.orderStatus }}</span></div>
            <div><span class="label">履约渠道（fulfillmentChannel）</span><span class="mono">{{ detail.fulfillmentChannel || '-' }}</span></div>
            <div><span class="label">退款状态（refundStatus）</span><span class="mono">{{ detail.refundStatus || '-' }}</span></div>
            <div><span class="label">下单时间（purchaseDate）</span><span class="mono">{{ formatDateTime(detail.purchaseDate) }}</span></div>
            <div><span class="label">最后更新时间（lastUpdateDate）</span><span class="mono">{{ formatDateTime(detail.lastUpdateDate) }}</span></div>
            <div><span class="label">订单金额</span><span class="mono">{{ detail.orderTotalAmount }} {{ detail.orderTotalCurrency }}</span></div>
          </div>
        </div>

        <div class="detail-section">
          <div class="section-title">订单明细（{{ detail.items.length }}）</div>
          <el-table :data="detail.items" size="small">
            <el-table-column label="明细 ID（orderItemId）" prop="orderItemId" width="160" show-overflow-tooltip>
              <template #default="{ row }"><span class="mono">{{ row.orderItemId }}</span></template>
            </el-table-column>
            <el-table-column label="商品 SKU（commoditySku）" prop="commoditySku" min-width="160" sortable show-overflow-tooltip />
            <el-table-column label="卖家 SKU（sellerSku）" prop="sellerSku" width="140" sortable show-overflow-tooltip />
            <el-table-column label="下单数" prop="quantityOrdered" width="88" align="right" sortable show-overflow-tooltip />
            <el-table-column label="发货数" prop="quantityShipped" width="88" align="right" sortable show-overflow-tooltip />
            <el-table-column label="退款数" prop="refundNum" width="88" align="right" sortable show-overflow-tooltip />
          </el-table>
        </div>

        <div class="detail-section">
          <div class="section-title">订单详情</div>
          <div v-if="hasVisibleDetail(detail)" class="kv-grid">
            <div><span class="label">邮编（postalCode）</span><span class="mono">{{ detail.postalCode || '-' }}</span></div>
            <div><span class="label">州 / 省（stateOrRegion）</span><span class="mono">{{ detail.stateOrRegion || '-' }}</span></div>
            <div><span class="label">城市（city）</span><span class="mono">{{ detail.city || '-' }}</span></div>
            <div><span class="label">收件人（receiverName）</span><span class="mono">{{ detail.receiverName || '-' }}</span></div>
            <div class="full-row"><span class="label">详细地址（detailAddress）</span><span>{{ detail.detailAddress || '-' }}</span></div>
            <div class="full-row">
              <span class="label">抓取时间（fetchedAt）</span>
              <span class="mono muted">{{ detail.detailFetchedAt ? formatDateTime(detail.detailFetchedAt) : '-' }}</span>
            </div>
          </div>
          <el-alert
            v-else-if="detail.detailFetchedAt"
            type="info"
            :closable="false"
            title="已拉取订单详情，但当前没有可展示的地址信息。"
          />
          <el-empty v-else description="尚未拉取订单详情" :image-size="60" />
        </div>
      </div>
    </el-dialog>
  </PageSectionCard>
</template>

<script setup lang="ts">
import { getOrderDetail, listDataShops, listOrders, type DataOrderDetail, type DataOrderSummary } from '@/api/data'
import { COUNTRY_OPTIONS } from '@/utils/countries'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import OrderDetailFetchAction from '@/components/sync/OrderDetailFetchAction.vue'
import type { TaskRun } from '@/api/task'
import type { TagType } from '@/utils/element'
import { formatDateTime } from '@/utils/format'
import { normalizeSortOrder, type SortChangeEvent, type SortState } from '@/utils/tableSort'
import { getActionErrorMessage } from '@/utils/apiError'
import { ElMessage } from 'element-plus'
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const rows = ref<DataOrderSummary[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const shopOptions = ref<string[]>([])
const loading = ref(false)
const sortState = ref<SortState>({ prop: 'purchaseDate', order: 'desc' })
const dateRange = ref<[string, string] | null>(null)
const detailFetchTaskId = ref<number | null>(null)
const filters = reactive({
  country: '',
  status: '',
  sku: '',
  shop: '',
})

const dialogVisible = ref(false)
const detail = ref<DataOrderDetail | null>(null)
let detailReqId = 0
let listReqId = 0
let skuReloadTimer: ReturnType<typeof setTimeout> | null = null

function clearSkuReloadTimer(): void {
  if (skuReloadTimer !== null) {
    clearTimeout(skuReloadTimer)
    skuReloadTimer = null
  }
}

async function reload(): Promise<void> {
  clearSkuReloadTimer()
  const myReqId = ++listReqId
  loading.value = true
  try {
    const resp = await listOrders({
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      country: filters.country || undefined,
      shop_id: filters.shop || undefined,
      status: filters.status || undefined,
      sku: filters.sku || undefined,
      page: page.value,
      page_size: pageSize.value,
      sort_by: sortState.value.prop,
      sort_order: sortState.value.order,
    })
    if (myReqId !== listReqId) return
    rows.value = resp.items
    total.value = resp.total
  } catch (err) {
    if (myReqId === listReqId) {
      ElMessage.error(getActionErrorMessage(err, '加载失败'))
    }
  } finally {
    if (myReqId === listReqId) {
      loading.value = false
    }
  }
}

async function loadShopOptions(): Promise<void> {
  try {
    const resp = await listDataShops()
    shopOptions.value = [...new Set(resp.items.map((item) => item.id))].sort()
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载店铺列表失败'))
  }
}

function reloadFirstPage(): void {
  clearSkuReloadTimer()
  page.value = 1
  void reload()
}

function scheduleSkuReload(): void {
  page.value = 1
  clearSkuReloadTimer()
  skuReloadTimer = setTimeout(() => {
    skuReloadTimer = null
    void reload()
  }, 300)
}

async function openDetail(row: DataOrderSummary): Promise<void> {
  const myReqId = ++detailReqId
  dialogVisible.value = true
  detail.value = null
  try {
    const data = await getOrderDetail(row.shopId, row.amazonOrderId)
    if (myReqId === detailReqId && dialogVisible.value) {
      detail.value = data
    }
  } catch (err) {
    if (myReqId === detailReqId) {
      dialogVisible.value = false
      ElMessage.error(getActionErrorMessage(err, '获取订单详情失败'))
    }
  }
}

function handleDetailFetchStarted(taskId: number): void {
  detailFetchTaskId.value = taskId
}

async function onDetailFetchDone(task: TaskRun): Promise<void> {
  detailFetchTaskId.value = null
  await reload()
  if (task.status === 'success') {
    ElMessage.success('详情获取完成，订单列表已刷新')
    return
  }
  ElMessage.error(task.error_msg || '详情获取失败，请查看任务状态')
}

function statusType(status: string): TagType {
  return (
    {
      Shipped: 'success',
      PartiallyShipped: 'success',
      Unshipped: 'warning',
      Pending: 'info',
      Canceled: 'danger',
    } as Record<string, TagType>
  )[status] || 'info'
}

const ORDER_STATUS_LABEL: Record<string, string> = {
  Shipped: '已发货',
  PartiallyShipped: '部分发货',
  Unshipped: '未发货',
  Pending: '待处理',
  Canceled: '已取消',
}

function statusLabel(status: string): string {
  return ORDER_STATUS_LABEL[status] || status
}

function hasVisibleDetail(detail: DataOrderDetail): boolean {
  return Boolean(
    detail.postalCode ||
      detail.stateOrRegion ||
      detail.city ||
      detail.receiverName ||
      detail.detailAddress
  )
}

function handleSortChange({ prop, order }: SortChangeEvent): void {
  const normalizedOrder = normalizeSortOrder(order)
  sortState.value = normalizedOrder && prop
    ? { prop, order: normalizedOrder }
    : { prop: 'purchaseDate', order: 'desc' }
  reloadFirstPage()
}

function handlePageChange(value: number): void {
  page.value = value
  void reload()
}

function handlePageSizeChange(value: number): void {
  pageSize.value = value
  page.value = 1
  void reload()
}

onMounted(() => {
  void loadShopOptions()
  void reload()
})

onBeforeUnmount(() => {
  clearSkuReloadTimer()
})
</script>

<style lang="scss" scoped>
.order-actions {
  display: flex;
  align-items: center;
  gap: $space-3;
  flex-wrap: wrap;
  width: 100%;
}

.order-filters {
  display: flex;
  align-items: center;
  gap: $space-3;
  flex-wrap: wrap;
}

.order-detail-fetch-slot {
  margin-left: auto;
}

.muted {
  color: $color-text-secondary;
}

.mono {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
}

.nowrap {
  white-space: nowrap;
}

.detail-body {
  display: flex;
  flex-direction: column;
  gap: $space-5;
}

.section-title {
  font-size: $font-size-xs;
  color: $color-text-secondary;
  font-weight: $font-weight-semibold;
  text-transform: uppercase;
  letter-spacing: $tracking-wider;
  margin-bottom: $space-3;
}

.kv-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: $space-3;
}

.kv-grid > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: $space-2 $space-3;
  background: $color-bg-subtle;
  border-radius: $radius-md;
}

.label {
  font-size: 11px;
  color: $color-text-secondary;
  text-transform: uppercase;
  letter-spacing: $tracking-wider;
  font-weight: $font-weight-semibold;
}

.full-row {
  grid-column: 1 / -1;
}

@media (max-width: 900px) {
  .order-actions,
  .order-filters {
    width: 100%;
  }

  .order-detail-fetch-slot {
    margin-left: 0;
  }
}
</style>
