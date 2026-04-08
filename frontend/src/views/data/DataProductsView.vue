<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <div class="title-block">
          <span class="card-title">在线产品信息</span>
          <span class="card-meta">product_listing 表 · 来自 /api/order/api/product/pageList.json</span>
        </div>
        <div class="actions">
          <el-input
            v-model="filters.sku"
            placeholder="commoditySku / sellerSku"
            clearable
            style="width: 220px"
            @keyup.enter="reload"
            @clear="reload"
          />
          <el-select v-model="filters.only_matched" placeholder="配对状态" clearable style="width: 130px" @change="reload">
            <el-option label="已配对" :value="true" />
            <el-option label="未配对" :value="false" />
          </el-select>
          <el-select v-model="filters.only_active" placeholder="在售状态" clearable style="width: 130px" @change="reload">
            <el-option label="在售" :value="true" />
            <el-option label="不在售" :value="false" />
          </el-select>
        </div>
      </div>
    </template>

    <el-table :data="rows" v-loading="loading">
      <el-table-column label="commoditySku" prop="commoditySku" min-width="180" />
      <el-table-column label="commodityId" prop="commodityId" width="120" />
      <el-table-column label="商品名" min-width="200">
        <template #default="{ row }">
          <span class="ellipsis">{{ row.commodityName || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="店铺/站点" width="180">
        <template #default="{ row }">
          <div class="meta-stack">
            <span>{{ row.shopId }}</span>
            <span class="meta-sub">{{ row.marketplaceId }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="sellerSku" prop="sellerSku" width="160" />
      <el-table-column label="day7" prop="day7SaleNum" width="80" align="right" />
      <el-table-column label="day14" prop="day14SaleNum" width="80" align="right" />
      <el-table-column label="day30" prop="day30SaleNum" width="80" align="right" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.isMatched" type="success" size="small">matched</el-tag>
          <el-tag v-else type="warning" size="small">unmatched</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最后同步" width="160">
        <template #default="{ row }">
          <span class="muted mono">{{ formatTime(row.lastSyncAt) }}</span>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100, 200]"
      layout="total, sizes, prev, pager, next"
      style="margin-top: 16px; justify-content: flex-end"
      @current-change="reload"
      @size-change="reload"
    />
  </el-card>
</template>

<script setup lang="ts">
import { listDataProductListings, type DataProductListing } from '@/api/data'
import dayjs from 'dayjs'
import { onMounted, reactive, ref } from 'vue'

const rows = ref<DataProductListing[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const loading = ref(false)
const filters = reactive({
  sku: '',
  only_matched: undefined as boolean | undefined,
  only_active: undefined as boolean | undefined
})

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listDataProductListings({
      sku: filters.sku || undefined,
      only_matched: filters.only_matched,
      only_active: filters.only_active,
      page: page.value,
      page_size: pageSize.value
    })
    rows.value = resp.items
    total.value = resp.total
  } finally {
    loading.value = false
  }
}

function formatTime(t: string): string {
  return dayjs(t).format('MM-DD HH:mm')
}

onMounted(reload)
</script>

<style lang="scss" scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-4;
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
}
.meta-stack {
  display: flex;
  flex-direction: column;
}
.meta-sub {
  font-size: $font-size-xs;
  color: $color-text-secondary;
}
.muted {
  color: $color-text-secondary;
}
.mono {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
}
.ellipsis {
  display: inline-block;
  max-width: 200px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
