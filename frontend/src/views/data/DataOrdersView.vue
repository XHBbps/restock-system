<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <div class="title-block">
          <span class="card-title">订单列表</span>
        </div>
        <div class="actions">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD"
            style="width: 260px"
            @change="reload"
          />
          <el-input
            v-model="filters.sku"
            placeholder="SKU / 订单号"
            clearable
            style="width: 200px"
            @keyup.enter="reload"
            @clear="reload"
          />
          <el-input
            v-model="filters.country"
            placeholder="国家"
            clearable
            maxlength="2"
            style="width: 100px"
            @keyup.enter="reload"
            @clear="reload"
          />
          <el-select v-model="filters.status" placeholder="状态" clearable style="width: 140px" @change="reload">
            <el-option label="Shipped" value="Shipped" />
            <el-option label="PartiallyShipped" value="PartiallyShipped" />
            <el-option label="Unshipped" value="Unshipped" />
            <el-option label="Pending" value="Pending" />
            <el-option label="Canceled" value="Canceled" />
          </el-select>
        </div>
      </div>
    </template>

    <el-table v-loading="loading" :data="rows">
      <el-table-column label="订单号" prop="amazonOrderId" width="220" sortable show-overflow-tooltip>
        <template #default="{ row }">
          <span class="mono">{{ row.amazonOrderId }}</span>
        </template>
      </el-table-column>
      <el-table-column label="店铺" prop="shopId" width="100" sortable show-overflow-tooltip>
        <template #default="{ row }">
          <span class="mono muted">{{ row.shopId }}</span>
        </template>
      </el-table-column>
      <el-table-column label="国家" width="80" align="center" sortable show-overflow-tooltip>
        <template #default="{ row }">
          <el-tag size="small">{{ row.countryCode }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="140" sortable show-overflow-tooltip>
        <template #default="{ row }">
          <el-tag :type="statusType(row.orderStatus)" size="small">{{ row.orderStatus }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="金额" width="120" align="right" sortable show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.orderTotalAmount">{{ row.orderTotalAmount }} {{ row.orderTotalCurrency }}</span>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="明细数" width="80" align="right" sortable show-overflow-tooltip>
        <template #default="{ row }">{{ row.itemCount }}</template>
      </el-table-column>
      <el-table-column label="详情状态" width="100" align="center" sortable show-overflow-tooltip>
        <template #default="{ row }">
          <el-tag v-if="row.hasDetail" type="success" size="small">已拉取</el-tag>
          <el-tag v-else type="info" size="small">未拉取</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="下单时间" width="160" sortable show-overflow-tooltip>
        <template #default="{ row }">
          <span class="muted mono">{{ formatTime(row.purchaseDate) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center" show-overflow-tooltip>
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
      @current-change="reload"
      @size-change="reload"
    />

    <el-dialog v-model="dialogVisible" :title="detail ? `订单 ${detail.amazonOrderId}` : '加载中...'" width="800px">
      <div v-if="detail" class="detail-body">
        <div class="detail-section">
          <div class="section-title">基本信息</div>
          <div class="kv-grid">
            <div><span class="label">shopId</span><span class="mono">{{ detail.shopId }}</span></div>
            <div><span class="label">marketplaceId</span><span class="mono">{{ detail.marketplaceId }}</span></div>
            <div><span class="label">countryCode</span><span class="mono">{{ detail.countryCode }}</span></div>
            <div><span class="label">orderStatus</span><span class="mono">{{ detail.orderStatus }}</span></div>
            <div><span class="label">fulfillmentChannel</span><span class="mono">{{ detail.fulfillmentChannel || '-' }}</span></div>
            <div><span class="label">refundStatus</span><span class="mono">{{ detail.refundStatus || '-' }}</span></div>
            <div><span class="label">purchaseDate</span><span class="mono">{{ formatTime(detail.purchaseDate) }}</span></div>
            <div><span class="label">lastUpdateDate</span><span class="mono">{{ formatTime(detail.lastUpdateDate) }}</span></div>
            <div><span class="label">总金额</span><span class="mono">{{ detail.orderTotalAmount }} {{ detail.orderTotalCurrency }}</span></div>
          </div>
        </div>

        <div class="detail-section">
          <div class="section-title">订单明细（{{ detail.items.length }}）</div>
          <el-table :data="detail.items" size="small">
            <el-table-column label="orderItemId" prop="orderItemId" width="160" show-overflow-tooltip>
              <template #default="{ row }"><span class="mono">{{ row.orderItemId }}</span></template>
            </el-table-column>
            <el-table-column label="commoditySku" prop="commoditySku" min-width="160" sortable show-overflow-tooltip />
            <el-table-column label="sellerSku" prop="sellerSku" width="140" sortable show-overflow-tooltip />
            <el-table-column label="ordered" prop="quantityOrdered" width="80" align="right" sortable show-overflow-tooltip />
            <el-table-column label="shipped" prop="quantityShipped" width="80" align="right" sortable show-overflow-tooltip />
            <el-table-column label="refund" prop="refundNum" width="80" align="right" sortable show-overflow-tooltip />
          </el-table>
        </div>

        <div class="detail-section">
          <div class="section-title">订单详情</div>
          <div v-if="detail.detailFetchedAt" class="kv-grid">
            <div><span class="label">postalCode</span><span class="mono">{{ detail.postalCode || '-' }}</span></div>
            <div><span class="label">stateOrRegion</span><span class="mono">{{ detail.stateOrRegion || '-' }}</span></div>
            <div><span class="label">city</span><span class="mono">{{ detail.city || '-' }}</span></div>
            <div><span class="label">receiverName</span><span class="mono">{{ detail.receiverName || '-' }}</span></div>
            <div class="full-row"><span class="label">detailAddress</span><span>{{ detail.detailAddress || '-' }}</span></div>
            <div class="full-row">
              <span class="label">fetchedAt</span>
              <span class="mono muted">{{ formatTime(detail.detailFetchedAt) }}</span>
            </div>
          </div>
          <el-empty v-else description="尚未拉取订单详情" :image-size="60" />
        </div>
      </div>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { getOrderDetail, listOrders, type DataOrderDetail, type DataOrderSummary } from '@/api/data'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import type { TagType } from '@/utils/element'
import dayjs from 'dayjs'
import { onMounted, reactive, ref } from 'vue'

const rows = ref<DataOrderSummary[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const loading = ref(false)
const dateRange = ref<[string, string] | null>(null)
const filters = reactive({
  country: '',
  status: '',
  sku: '',
})

const dialogVisible = ref(false)
const detail = ref<DataOrderDetail | null>(null)
let detailReqId = 0

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listOrders({
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      country: filters.country || undefined,
      status: filters.status || undefined,
      sku: filters.sku || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = resp.items
    total.value = resp.total
  } finally {
    loading.value = false
  }
}

async function openDetail(row: DataOrderSummary): Promise<void> {
  const myReqId = ++detailReqId
  dialogVisible.value = true
  detail.value = null
  const data = await getOrderDetail(row.shopId, row.amazonOrderId)
  if (myReqId === detailReqId && dialogVisible.value) {
    detail.value = data
  }
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

function formatTime(value: string): string {
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

onMounted(reload)
</script>

<style lang="scss" scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-4;
  flex-wrap: wrap;
}

.title-block {
  display: flex;
  flex-direction: column;
}

.card-title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
  letter-spacing: $tracking-tight;
}

.card-meta {
  font-size: $font-size-xs;
  color: $color-text-secondary;
  font-family: $font-family-mono;
  margin-top: 2px;
}

.actions {
  display: flex;
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
</style>
