<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <div class="title-block">
          <span class="card-title">库存明细</span>
        </div>
        <div class="actions">
          <el-input
            v-model="filters.sku"
            placeholder="commoditySku"
            clearable
            style="width: 220px"
            @keyup.enter="reload"
            @clear="reload"
          />
          <el-input
            v-model="filters.country"
            placeholder="国家（JP/US/...）"
            clearable
            maxlength="2"
            style="width: 140px"
            @keyup.enter="reload"
            @clear="reload"
          />
          <el-switch v-model="filters.only_nonzero" active-text="仅非零" @change="reload" />
        </div>
      </div>
    </template>

    <el-table v-loading="loading" :data="rows">
      <el-table-column label="SKU" prop="commoditySku" min-width="180" sortable show-overflow-tooltip />
      <el-table-column label="商品名称" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="ellipsis">{{ row.commodityName || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="仓库" min-width="180" sortable show-overflow-tooltip>
        <template #default="{ row }">
          <div class="meta-stack">
            <span>{{ row.warehouseName }}</span>
            <span class="meta-sub">{{ row.warehouseId }} / type={{ row.warehouseType }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="国家" prop="country" width="80" align="center" sortable show-overflow-tooltip>
        <template #default="{ row }">
          <el-tag v-if="row.country" size="small">{{ row.country }}</el-tag>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="可用库存" prop="stockAvailable" width="140" align="right" sortable show-overflow-tooltip>
        <template #default="{ row }">
          <strong>{{ row.stockAvailable }}</strong>
        </template>
      </el-table-column>
      <el-table-column label="占用库存" prop="stockOccupy" width="120" align="right" sortable show-overflow-tooltip />
      <el-table-column label="更新时间" width="160" sortable show-overflow-tooltip>
        <template #default="{ row }">
          <span class="muted mono">{{ formatTime(row.updatedAt) }}</span>
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
import { listInventory, type DataInventoryItem } from '@/api/data'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import dayjs from 'dayjs'
import { onMounted, reactive, ref } from 'vue'

const rows = ref<DataInventoryItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const loading = ref(false)
const filters = reactive({
  sku: '',
  country: '',
  only_nonzero: true,
})

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listInventory({
      sku: filters.sku || undefined,
      country: filters.country || undefined,
      only_nonzero: filters.only_nonzero,
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
  align-items: center;
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
