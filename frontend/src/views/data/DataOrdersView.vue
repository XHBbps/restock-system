<template>
  <PageSectionCard title="订单列表">
    <template #actions>
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
          style="width: 220px"
          @input="scheduleSkuReload"
          @keyup.enter="reloadFirstPage"
          @clear="reloadFirstPage"
        />
        <el-select
          v-model="filters.country"
          placeholder="国家"
          clearable
          filterable
          style="width: 140px"
          @change="reloadFirstPage"
        >
          <el-option v-for="c in countryOptions" :key="c.code" :label="c.label" :value="c.code" />
        </el-select>
        <el-select
          v-model="filters.shop"
          placeholder="店铺"
          clearable
          filterable
          style="width: 160px"
          @change="reloadFirstPage"
        >
          <el-option v-for="s in shopOptions" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-select
          v-model="filters.platform"
          placeholder="平台"
          clearable
          filterable
          style="width: 150px"
          @change="reloadFirstPage"
        >
          <el-option
            v-for="platform in platformOptions"
            :key="platform"
            :label="platform"
            :value="platform"
          />
        </el-select>
        <el-select
          v-model="filters.status"
          placeholder="包裹状态"
          clearable
          style="width: 150px"
          @change="reloadFirstPage"
        >
          <el-option
            v-for="item in packageStatusOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </div>
    </template>

    <el-table
      v-if="!isMobile"
      v-loading="loading"
      :data="rows"
      table-layout="auto"
      @sort-change="handleSortChange"
    >
      <el-table-column
        label="订单号"
        prop="amazonOrderId"
        min-width="190"
        sortable="custom"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <span class="mono nowrap">{{ row.amazonOrderId }}</span>
        </template>
      </el-table-column>
      <el-table-column
        label="店铺"
        prop="shopName"
        min-width="150"
        sortable="custom"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <span>{{ row.shopName || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column
        label="平台"
        prop="orderPlatform"
        min-width="112"
        sortable="custom"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <el-tag size="small" effect="plain" type="info" class="nowrap">{{
            row.orderPlatform
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="国家" prop="countryCode" width="72" align="center" sortable="custom">
        <template #default="{ row }">
          <el-tag size="small">{{ row.countryCode }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column
        label="邮编"
        prop="postalCode"
        width="108"
        sortable="custom"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <span class="mono nowrap">{{ row.postalCode || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="包裹状态" prop="packageStatus" width="132" sortable="custom">
        <template #default="{ row }">
          <el-tag :type="statusType(row.packageStatus || row.orderStatus)" size="small">
            {{ statusLabel(row.packageStatus || row.orderStatus) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="明细数" prop="itemCount" width="80" align="right" sortable="custom">
        <template #default="{ row }">{{ row.itemCount }}</template>
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

    <MobileRecordList
      v-else
      :items="rows"
      :loading="loading"
      row-key="amazonOrderId"
      empty-text="暂无订单"
    >
      <template #default="{ item: row }">
        <div class="mobile-order-card">
          <div class="mobile-card-head">
            <div class="mobile-card-title mono">{{ row.amazonOrderId }}</div>
            <el-tag :type="statusType(row.packageStatus || row.orderStatus)" size="small">
              {{ statusLabel(row.packageStatus || row.orderStatus) }}
            </el-tag>
          </div>
          <div class="mobile-card-meta">
            <span>{{ row.shopName || '-' }}</span>
            <el-tag size="small" effect="plain" type="info">{{ row.orderPlatform }}</el-tag>
            <el-tag size="small">{{ row.countryCode }}</el-tag>
          </div>
          <div class="mobile-kv-grid">
            <div>
              <span>明细数</span>
              <strong>{{ row.itemCount }}</strong>
            </div>
            <div>
              <span>邮编</span>
              <strong class="mono">{{ row.postalCode || '-' }}</strong>
            </div>
            <div class="mobile-kv-grid__wide">
              <span>下单时间</span>
              <strong class="mono">{{ formatDateTime(row.purchaseDate) }}</strong>
            </div>
          </div>
          <div class="mobile-card-actions">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          </div>
        </div>
      </template>
    </MobileRecordList>

    <TablePaginationBar
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100, 200]"
      @current-change="handlePageChange"
      @size-change="handlePageSizeChange"
    />

    <el-dialog
      v-model="dialogVisible"
      :title="detail ? `订单详情 · ${detail.amazonOrderId}` : '加载中...'"
      width="800px"
      :fullscreen="isMobile"
      class="order-detail-dialog"
    >
      <div v-if="detail" class="detail-body">
        <div class="detail-section">
          <div class="section-title">基本信息</div>
          <div class="kv-grid">
            <div>
              <span class="label">包裹状态</span
              ><span>{{ statusLabel(detail.packageStatus || detail.orderStatus) }}</span>
            </div>
            <div>
              <span class="label">店铺</span><span>{{ detail.shopName || '-' }}</span>
            </div>
            <div>
              <span class="label">平台</span><span>{{ detail.orderPlatform }}</span>
            </div>
            <div>
              <span class="label">国家</span><span class="mono">{{ detail.countryCode }}</span>
            </div>
            <div>
              <span class="label">邮编</span
              ><span class="mono">{{ detail.postalCode || '-' }}</span>
            </div>
            <div>
              <span class="label">订单号</span><span class="mono">{{ detail.amazonOrderId }}</span>
            </div>
            <div>
              <span class="label">下单时间</span
              ><span class="mono">{{ formatDateTime(detail.purchaseDate) }}</span>
            </div>
            <div>
              <span class="label">最后更新时间</span
              ><span class="mono">{{ formatDateTime(detail.lastUpdateDate) }}</span>
            </div>
            <div>
              <span class="label">订单金额</span>
              <span class="mono">{{
                detail.orderTotalAmount
                  ? `${detail.orderTotalAmount} ${detail.orderTotalCurrency || ''}`
                  : '-'
              }}</span>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <div class="section-title">订单明细（{{ detail.items.length }}）</div>
          <el-table :data="detail.items" size="small">
            <el-table-column label="明细 ID" prop="orderItemId" width="160" show-overflow-tooltip>
              <template #default="{ row }"
                ><span class="mono">{{ row.orderItemId }}</span></template
              >
            </el-table-column>
            <el-table-column
              label="商品 SKU"
              prop="commoditySku"
              min-width="160"
              sortable
              show-overflow-tooltip
            />
            <el-table-column
              label="下单数"
              prop="quantityOrdered"
              width="88"
              align="right"
              sortable
            />
            <el-table-column
              label="计算数"
              prop="quantityShipped"
              width="88"
              align="right"
              sortable
            />
            <el-table-column label="退款数" prop="refundNum" width="88" align="right" sortable />
          </el-table>
        </div>
      </div>
    </el-dialog>
  </PageSectionCard>
</template>

<script setup lang="ts">
import { getCountryOptions, type CountryOption } from '@/api/config'
import {
  getOrderDetail,
  listDataShops,
  listOrderPlatforms,
  listOrders,
  type DataOrderDetail,
  type DataOrderSummary
} from '@/api/data'
import MobileRecordList from '@/components/MobileRecordList.vue'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { useResponsive } from '@/composables/useResponsive'
import { getActionErrorMessage } from '@/utils/apiError'
import { COUNTRY_OPTIONS } from '@/utils/countries'
import type { TagType } from '@/utils/element'
import { formatDateTime } from '@/utils/format'
import { normalizeSortOrder, type SortChangeEvent, type SortState } from '@/utils/tableSort'
import { ElMessage } from 'element-plus'
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const packageStatusOptions = [
  { label: '待审核', value: 'to_audit' },
  { label: '待处理', value: 'to_process' },
  { label: '申请运单号', value: 'apply_track_no' },
  { label: '待打印', value: 'to_print' },
  { label: '已发货', value: 'has_shipped' },
  { label: '已作废', value: 'has_canceled' }
]

const rows = ref<DataOrderSummary[]>([])
const { isMobile } = useResponsive()
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const shopOptions = ref<Array<{ id: string; name: string }>>([])
const platformOptions = ref<string[]>([])
const countryOptions = ref<CountryOption[]>(
  COUNTRY_OPTIONS.map((option) => ({
    ...option,
    builtin: true,
    observed: false,
    can_be_eu_member: !['EU', 'ZZ'].includes(option.code)
  }))
)
const loading = ref(false)
const sortState = ref<SortState>({ prop: 'purchaseDate', order: 'desc' })
const dateRange = ref<[string, string] | null>(null)
const filters = reactive({
  country: '',
  platform: '',
  status: '',
  sku: '',
  shop: ''
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
      platform: filters.platform || undefined,
      status: filters.status || undefined,
      sku: filters.sku || undefined,
      page: page.value,
      page_size: pageSize.value,
      sort_by: sortState.value.prop,
      sort_order: sortState.value.order
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
    shopOptions.value = resp.items
      .map((item) => ({ id: item.id, name: item.name || item.id }))
      .sort((a, b) => a.name.localeCompare(b.name))
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载店铺列表失败'))
  }
}

async function loadPlatformOptions(): Promise<void> {
  try {
    platformOptions.value = await listOrderPlatforms()
  } catch {
    platformOptions.value = []
  }
}

async function loadCountryOptions(): Promise<void> {
  try {
    const resp = await getCountryOptions()
    countryOptions.value = resp.items
  } catch {
    // Keep builtin country options as fallback.
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
    const data = await getOrderDetail(row.shopId, row.amazonOrderId, row.packageSn)
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

function statusType(status: string): TagType {
  return (
    (
      {
        has_shipped: 'success',
        has_canceled: 'danger',
        to_audit: 'warning',
        to_process: 'warning',
        apply_track_no: 'info',
        to_print: 'warning',
        Shipped: 'success',
        PartiallyShipped: 'success',
        Unshipped: 'warning',
        Pending: 'info',
        Canceled: 'danger',
        Unknown: 'info'
      } as Record<string, TagType>
    )[status] || 'info'
  )
}

const ORDER_STATUS_LABEL: Record<string, string> = {
  has_shipped: '已发货',
  has_canceled: '已作废',
  to_audit: '待审核',
  to_process: '待处理',
  apply_track_no: '申请运单号',
  to_print: '待打印',
  Shipped: '已发货',
  PartiallyShipped: '部分发货',
  Unshipped: '未发货',
  Pending: '待处理',
  Canceled: '已取消',
  Unknown: '未知'
}

function statusLabel(status: string): string {
  return ORDER_STATUS_LABEL[status] || status
}

function handleSortChange({ prop, order }: SortChangeEvent): void {
  const normalizedOrder = normalizeSortOrder(order)
  sortState.value =
    normalizedOrder && prop
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
  void loadCountryOptions()
  void loadShopOptions()
  void loadPlatformOptions()
  void reload()
})

onBeforeUnmount(() => {
  clearSkuReloadTimer()
})
</script>

<style lang="scss" scoped>
.order-filters {
  display: flex;
  align-items: center;
  gap: $space-3;
  flex-wrap: wrap;
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

@media (max-width: 900px) {
  .order-filters {
    width: 100%;
  }
}

@media (max-width: 767px) {
  .order-filters {
    align-items: stretch;

    :deep(.el-input),
    :deep(.el-select),
    :deep(.el-date-editor) {
      width: 100% !important;
    }
  }

  .mobile-order-card {
    display: flex;
    flex-direction: column;
    gap: $space-3;
  }

  .mobile-card-head,
  .mobile-card-meta,
  .mobile-card-actions {
    display: flex;
    align-items: center;
    gap: $space-2;
  }

  .mobile-card-head {
    justify-content: space-between;
  }

  .mobile-card-title {
    min-width: 0;
    overflow: hidden;
    color: $color-text-primary;
    font-weight: $font-weight-semibold;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mobile-card-meta {
    flex-wrap: wrap;
    color: $color-text-secondary;
    font-size: $font-size-xs;
  }

  .mobile-kv-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: $space-2;
  }

  .mobile-kv-grid > div {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    padding: $space-2;
    border-radius: $radius-md;
    background: $color-bg-subtle;
  }

  .mobile-kv-grid span {
    color: $color-text-secondary;
    font-size: 11px;
  }

  .mobile-kv-grid strong {
    min-width: 0;
    overflow: hidden;
    font-size: $font-size-xs;
    font-weight: $font-weight-medium;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mobile-kv-grid__wide {
    grid-column: 1 / -1;
  }

  .mobile-card-actions {
    justify-content: flex-end;
  }

  .kv-grid {
    grid-template-columns: 1fr;
  }

  :global(.order-detail-dialog.is-fullscreen) {
    display: flex;
    flex-direction: column;
  }

  :global(.order-detail-dialog.is-fullscreen .el-dialog__body) {
    flex: 1;
    max-height: none;
  }
}
</style>
