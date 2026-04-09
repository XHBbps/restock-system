<template>
  <PageSectionCard title="店铺数据" description="展示赛狐店铺主数据、授权状态和同步参与状态。">
    <el-table v-loading="loading" :data="pagedRows">
      <el-table-column label="店铺 ID" prop="id" width="110" />
      <el-table-column label="店铺名称" prop="name" min-width="220" />
      <el-table-column label="Seller ID" prop="sellerId" width="180">
        <template #default="{ row }">
          <span class="mono muted">{{ row.sellerId || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="区域" prop="region" width="100" align="center" />
      <el-table-column label="站点" prop="marketplaceId" width="120" />
      <el-table-column label="授权状态" width="140">
        <template #default="{ row }">
          <StatusTag :meta="getShopStatusMeta(row.status)" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="参与同步" width="120" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.syncEnabled" type="success" size="small">是</el-tag>
          <el-tag v-else type="info" size="small">否</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="广告状态" prop="adStatus" width="120" />
      <el-table-column label="最近同步时间" width="160">
        <template #default="{ row }">
          <span class="muted mono">{{ row.lastSyncAt ? formatTime(row.lastSyncAt) : '-' }}</span>
        </template>
      </el-table-column>
    </el-table>

    <TablePaginationBar
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="rows.length"
    />
  </PageSectionCard>
</template>

<script setup lang="ts">
import { listDataShops, type DataShop } from '@/api/data'
import PageSectionCard from '@/components/PageSectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { getShopStatusMeta } from '@/utils/status'
import dayjs from 'dayjs'
import { computed, onMounted, ref } from 'vue'

const rows = ref<DataShop[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return rows.value.slice(start, start + pageSize.value)
})

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listDataShops()
    rows.value = resp.items
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
.muted {
  color: $color-text-secondary;
}

.mono {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
}
</style>
