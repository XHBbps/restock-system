<template>
  <el-card shadow="never">
    <template #header>
      <div class="title-block">
        <span class="card-title">店铺列表</span>
        <span class="card-meta">shop · 来自 /api/shop/pageList.json</span>
      </div>
    </template>

    <el-table :data="rows" v-loading="loading">
      <el-table-column label="id" prop="id" width="100" />
      <el-table-column label="name" prop="name" min-width="200" />
      <el-table-column label="sellerId" prop="sellerId" width="180">
        <template #default="{ row }">
          <span class="mono muted">{{ row.sellerId || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="region" prop="region" width="80" align="center" />
      <el-table-column label="marketplaceId" prop="marketplaceId" width="120" />
      <el-table-column label="status" width="140">
        <template #default="{ row }">
          <el-tag v-if="row.status === '0'" type="success" size="small">0 正常</el-tag>
          <el-tag v-else-if="row.status === '1'" type="danger" size="small">1 授权失效</el-tag>
          <el-tag v-else-if="row.status === '2'" type="warning" size="small">2 SP 失效</el-tag>
          <el-tag v-else type="info" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="syncEnabled" width="120" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.syncEnabled" type="success" size="small">是</el-tag>
          <el-tag v-else type="info" size="small">否</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="adStatus" prop="adStatus" width="120" />
      <el-table-column label="lastSyncAt" width="160">
        <template #default="{ row }">
          <span class="muted mono">{{ row.lastSyncAt ? formatTime(row.lastSyncAt) : '-' }}</span>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { listDataShops, type DataShop } from '@/api/data'
import dayjs from 'dayjs'
import { onMounted, ref } from 'vue'

const rows = ref<DataShop[]>([])
const loading = ref(false)

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listDataShops()
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
