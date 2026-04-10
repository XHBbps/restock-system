<template>
  <PageSectionCard title="店铺">
    <template #actions>
      <el-button :loading="refreshing" @click="refresh">刷新店铺</el-button>
    </template>

    <el-table v-loading="loading" :data="pagedRows">
      <el-table-column label="店铺 ID" prop="id" width="110" />
      <el-table-column label="店铺名称" prop="name" min-width="220" />
      <el-table-column label="卖家ID" prop="sellerId" width="180">
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
          <el-switch
            :model-value="row.syncEnabled"
            :disabled="row.status !== '0'"
            @change="(v) => toggleSync(row, normalizeSwitchValue(v))"
          />
        </template>
      </el-table-column>
      <el-table-column label="广告状态" prop="adStatus" width="120" />
      <el-table-column label="最近同步" width="140">
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

    <TaskProgress v-if="refreshTaskId" :task-id="refreshTaskId" @terminal="onRefreshDone" />
  </PageSectionCard>
</template>

<script setup lang="ts">
import { listDataShops, type DataShop } from '@/api/data'
import { patchShop, refreshShops } from '@/api/config'
import PageSectionCard from '@/components/PageSectionCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import { normalizeSwitchValue } from '@/utils/element'
import { getShopStatusMeta } from '@/utils/status'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

const rows = ref<DataShop[]>([])
const loading = ref(false)
const refreshing = ref(false)
const refreshTaskId = ref<number | null>(null)
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

async function toggleSync(row: DataShop, value: boolean): Promise<void> {
  try {
    await patchShop(row.id, value)
    row.syncEnabled = value
    ElMessage.success(`${row.name} 已${value ? '启用' : '禁用'}同步。`)
  } catch {
    ElMessage.error('更新失败。')
  }
}

async function refresh(): Promise<void> {
  refreshing.value = true
  try {
    const resp = await refreshShops()
    refreshTaskId.value = resp.task_id
  } catch {
    ElMessage.error('刷新失败。')
  } finally {
    refreshing.value = false
  }
}

async function onRefreshDone(): Promise<void> {
  refreshTaskId.value = null
  await reload()
  ElMessage.success('店铺列表已更新。')
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
