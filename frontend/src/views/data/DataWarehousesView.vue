<template>
  <el-card shadow="never">
    <template #header>
      <div class="title-block">
        <span class="card-title">仓库列表</span>
        <span class="card-meta">warehouse · 来自 /api/warehouseManage/warehouseList.json</span>
      </div>
    </template>

    <el-table :data="rows" v-loading="loading">
      <el-table-column label="id" prop="id" width="120" />
      <el-table-column label="name" prop="name" min-width="240" />
      <el-table-column label="type" width="100" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.type === 1" type="success" size="small">1 国内仓</el-tag>
          <el-tag v-else-if="row.type === 0" size="small">0 默认</el-tag>
          <el-tag v-else-if="row.type === 2" size="small">2 FBA</el-tag>
          <el-tag v-else-if="row.type === 3" size="small">3 海外仓</el-tag>
          <el-tag v-else-if="row.type === -1" type="info" size="small">-1 虚拟</el-tag>
          <el-tag v-else type="info" size="small">{{ row.type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="country (手动维护)" width="180">
        <template #default="{ row }">
          <el-tag v-if="row.country" size="small">{{ row.country }}</el-tag>
          <el-tag v-else type="warning" size="small">待指定</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="replenishSite (原始)" prop="replenishSite" width="180">
        <template #default="{ row }">
          <span class="muted mono">{{ row.replenishSite || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="lastSyncAt" width="160">
        <template #default="{ row }">
          <span class="muted mono">{{ formatTime(row.lastSyncAt) }}</span>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { listDataWarehouses, type DataWarehouse } from '@/api/data'
import dayjs from 'dayjs'
import { onMounted, ref } from 'vue'

const rows = ref<DataWarehouse[]>([])
const loading = ref(false)

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listDataWarehouses()
    rows.value = resp.items
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
.muted {
  color: $color-text-secondary;
}
.mono {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
}
</style>
