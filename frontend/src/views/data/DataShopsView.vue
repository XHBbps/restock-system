<template>
  <PageSectionCard title="店铺">
    <template #actions>
      <el-input v-model="filters.keyword" placeholder="搜索店铺名/ID" clearable style="width: 180px" />
      <el-select v-model="filters.region" placeholder="区域" clearable style="width: 120px">
        <el-option label="NA" value="na" />
        <el-option label="EU" value="eu" />
        <el-option label="FE" value="fe" />
        <el-option label="IN" value="in" />
      </el-select>
      <el-button v-if="auth.hasPermission('sync:operate')" :loading="refreshing" @click="refresh">刷新店铺</el-button>
    </template>

    <el-table v-loading="loading" :data="pagedRows" style="width: 100%" :scrollbar-always-on="true">
      <el-table-column label="店铺 ID" prop="id" width="100" show-overflow-tooltip />
      <el-table-column label="店铺名称" prop="name" min-width="180" show-overflow-tooltip />
      <el-table-column label="卖家ID" width="150">
        <template #default="{ row }">
          <span class="mono muted">{{ row.sellerId || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="区域" width="80" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.region" :type="regionTagType(row.region)" size="small">
            {{ row.region.toUpperCase() }}
          </el-tag>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="站点" min-width="170">
        <template #default="{ row }">
          <el-tag v-if="row.marketplaceId" size="small">
            {{ row.marketplaceId }}
          </el-tag>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="授权状态" width="100">
        <template #default="{ row }">
          <StatusTag :meta="getShopStatusMeta(row.status)" size="small" />
        </template>
      </el-table-column>
      <el-table-column label="订单同步" width="90" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="row.syncEnabled"
            :disabled="row.status !== '0'"
            @change="(v) => toggleSync(row, normalizeSwitchValue(v))"
          />
        </template>
      </el-table-column>
      <el-table-column label="广告状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.adStatus" :type="adStatusTagType(row.adStatus)" size="small">
            {{ adStatusLabel(row.adStatus) }}
          </el-tag>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="同步时间" width="168">
        <template #default="{ row }">
          <span class="muted mono">{{ row.lastSyncAt ? formatUpdateTime(row.lastSyncAt) : '-' }}</span>
        </template>
      </el-table-column>
    </el-table>

    <TablePaginationBar
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="filteredRows.length"
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
import { formatUpdateTime } from '@/utils/format'
import { normalizeSwitchValue } from '@/utils/element'
import { getShopStatusMeta } from '@/utils/status'
import { useAuthStore } from '@/stores/auth'
import { getActionErrorMessage } from '@/utils/apiError'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'

const auth = useAuthStore()

const rows = ref<DataShop[]>([])
const loading = ref(false)
const refreshing = ref(false)
const refreshTaskId = ref<number | null>(null)
const page = ref(1)
const pageSize = ref(10)
const filters = reactive({
  keyword: '',
  region: '' as string,
})

const REGION_COLORS: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
  na: 'primary',
  eu: 'success',
  fe: 'warning',
  in: 'danger',
}

function regionTagType(region: string): 'primary' | 'success' | 'warning' | 'danger' | 'info' {
  return REGION_COLORS[region.toLowerCase()] || 'info'
}

const AD_STATUS_MAP: Record<string, string> = {
  auth: '已授权',
  unauth: '未授权',
  expired: '已过期',
}

function adStatusLabel(status: string): string {
  return AD_STATUS_MAP[status.toLowerCase()] || status
}

function adStatusTagType(status: string): 'success' | 'warning' | 'info' {
  const s = status.toLowerCase()
  if (s === 'auth') return 'success'
  if (s === 'expired') return 'warning'
  return 'info'
}

const filteredRows = computed(() => {
  let result = rows.value
  if (filters.keyword) {
    const q = filters.keyword.toLowerCase()
    result = result.filter((r) => r.name.toLowerCase().includes(q) || r.id.toLowerCase().includes(q))
  }
  if (filters.region) {
    result = result.filter((r) => r.region?.toLowerCase() === filters.region)
  }
  return result
})

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRows.value.slice(start, start + pageSize.value)
})

watch(() => [filters.keyword, filters.region], () => { page.value = 1 })

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listDataShops()
    rows.value = resp.items
  } finally {
    loading.value = false
  }
}

async function toggleSync(row: DataShop, value: boolean): Promise<void> {
  try {
    await patchShop(row.id, value)
    row.syncEnabled = value
    ElMessage.success(`${row.name} 已${value ? '启用' : '禁用'}同步。`)
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '更新失败。'))
  }
}

async function refresh(): Promise<void> {
  refreshing.value = true
  try {
    const resp = await refreshShops()
    refreshTaskId.value = resp.task_id
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '刷新失败。'))
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
