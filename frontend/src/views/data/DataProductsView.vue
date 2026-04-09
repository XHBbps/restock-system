<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <div class="title-block">
          <span class="card-title">在线商品信息</span>
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
          <el-select v-model="filters.only_matched" placeholder="匹配状态" clearable style="width: 130px" @change="reload">
            <el-option label="已匹配" :value="true" />
            <el-option label="未匹配" :value="false" />
          </el-select>
          <el-select v-model="filters.only_active" placeholder="在售状态" clearable style="width: 130px" @change="reload">
            <el-option label="在售" :value="true" />
            <el-option label="不在售" :value="false" />
          </el-select>
        </div>
      </div>
    </template>

    <el-table v-loading="loading" :data="rows">
      <el-table-column label="SKU" prop="commoditySku" min-width="180" sortable show-overflow-tooltip />
      <el-table-column label="商品 ID" prop="commodityId" width="120" sortable show-overflow-tooltip />
      <el-table-column label="商品名称" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="ellipsis">{{ row.commodityName || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="店铺/站点" width="180" sortable show-overflow-tooltip>
        <template #default="{ row }">
          <div class="meta-stack">
            <span>{{ row.shopId }}</span>
            <span class="meta-sub">{{ row.marketplaceId }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="Seller SKU" prop="sellerSku" width="160" sortable show-overflow-tooltip />
      <el-table-column label="7天销量" prop="day7SaleNum" width="90" align="right" sortable show-overflow-tooltip />
      <el-table-column label="14天销量" prop="day14SaleNum" width="90" align="right" sortable show-overflow-tooltip />
      <el-table-column label="30天销量" prop="day30SaleNum" width="90" align="right" sortable show-overflow-tooltip />
      <el-table-column label="匹配状态" width="100" sortable show-overflow-tooltip>
        <template #default="{ row }">
          <el-tag v-if="row.isMatched" type="success" size="small">已匹配</el-tag>
          <el-tag v-else type="warning" size="small">未匹配</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最后同步" width="160" sortable show-overflow-tooltip>
        <template #default="{ row }">
          <span class="muted mono">{{ formatTime(row.lastSyncAt) }}</span>
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
  </el-card>
</template>

<script setup lang="ts">
import { listDataProductListings, type DataProductListing } from '@/api/data'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
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
  only_active: undefined as boolean | undefined,
})

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listDataProductListings({
      sku: filters.sku || undefined,
      only_matched: filters.only_matched,
      only_active: filters.only_active,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = resp.items
    total.value = resp.total
  } finally {
    loading.value = false
  }
}

function formatTime(value: string): string {
  return dayjs(value).format('MM-DD HH:mm')
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
