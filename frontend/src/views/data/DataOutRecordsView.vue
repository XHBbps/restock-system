<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <div class="title-block">
          <span class="card-title">其他出库（在途数据）</span>
          <span class="card-meta">in_transit_record · 来自 /api/warehouseInOut/outRecords.json (searchField=remark, searchValue=在途中)</span>
        </div>
        <div class="actions">
          <el-input
            v-model="filters.sku"
            placeholder="commoditySku"
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
            style="width: 120px"
            @keyup.enter="reload"
            @clear="reload"
          />
          <el-select v-model="filters.is_in_transit" placeholder="状态" style="width: 130px" @change="reload">
            <el-option label="在途中" :value="true" />
            <el-option label="已消失" :value="false" />
          </el-select>
        </div>
      </div>
    </template>

    <el-table :data="rows" v-loading="loading" :expand-row-keys="expandedKeys" row-key="saihuOutRecordId">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="expand-panel">
            <div class="expand-title">出库单明细 ({{ row.items.length }} 项)</div>
            <el-table :data="row.items" size="small">
              <el-table-column label="commoditySku" prop="commoditySku" />
              <el-table-column label="goods (在途数)" prop="goods" width="160" align="right" />
            </el-table>
            <div class="expand-meta">
              备注: <code>{{ row.remark || '-' }}</code>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="出库单号" prop="outWarehouseNo" min-width="160" />
      <el-table-column label="saihuOutRecordId" prop="saihuOutRecordId" width="160" />
      <el-table-column label="目标仓" min-width="200">
        <template #default="{ row }">
          <div class="meta-stack">
            <span>{{ row.targetWarehouseName || '-' }}</span>
            <span class="meta-sub">{{ row.targetWarehouseId || '未知' }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="目的国" width="90" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.targetCountry" size="small">{{ row.targetCountry }}</el-tag>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="明细数" width="90" align="right">
        <template #default="{ row }">{{ row.items.length }}</template>
      </el-table-column>
      <el-table-column label="总在途" width="100" align="right">
        <template #default="{ row }">
          <strong>{{ sumGoods(row) }}</strong>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.isInTransit" type="success" size="small">在途中</el-tag>
          <el-tag v-else type="info" size="small">已消失</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最后同步" width="160">
        <template #default="{ row }">
          <span class="muted mono">{{ formatTime(row.lastSeenAt) }}</span>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100]"
      layout="total, sizes, prev, pager, next"
      style="margin-top: 16px; justify-content: flex-end"
      @current-change="reload"
      @size-change="reload"
    />
  </el-card>
</template>

<script setup lang="ts">
import { listOutRecords, type DataOutRecord } from '@/api/data'
import dayjs from 'dayjs'
import { onMounted, reactive, ref } from 'vue'

const rows = ref<DataOutRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const loading = ref(false)
const expandedKeys = ref<string[]>([])
const filters = reactive({
  sku: '',
  country: '',
  is_in_transit: true as boolean | undefined
})

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listOutRecords({
      sku: filters.sku || undefined,
      country: filters.country || undefined,
      is_in_transit: filters.is_in_transit,
      page: page.value,
      page_size: pageSize.value
    })
    rows.value = resp.items
    total.value = resp.total
  } finally {
    loading.value = false
  }
}

function sumGoods(row: DataOutRecord): number {
  return row.items.reduce((sum, it) => sum + it.goods, 0)
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
.expand-panel {
  padding: $space-3 $space-4;
  background: $color-bg-subtle;
  border-radius: $radius-md;
}
.expand-title {
  font-size: $font-size-xs;
  color: $color-text-secondary;
  font-weight: $font-weight-semibold;
  text-transform: uppercase;
  letter-spacing: $tracking-wider;
  margin-bottom: $space-2;
}
.expand-meta {
  margin-top: $space-2;
  font-size: $font-size-xs;
  color: $color-text-secondary;
  code {
    font-family: $font-family-mono;
    background: $color-bg-card;
    padding: 2px 6px;
    border-radius: $radius-sm;
    border: 1px solid $color-border-default;
  }
}
.meta-stack {
  display: flex;
  flex-direction: column;
}
.meta-sub {
  font-size: $font-size-xs;
  color: $color-text-secondary;
  font-family: $font-family-mono;
}
.muted {
  color: $color-text-secondary;
}
.mono {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
}
</style>
