<template>
  <div class="shop-view">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">店铺管理</div>
            <div class="card-meta">店铺状态统一显示为业务含义，不再直接暴露状态码。</div>
          </div>
          <el-button :loading="refreshing" @click="refresh">手动刷新（拉取赛狐）</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="pagedRows">
        <el-table-column label="店铺" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <strong>{{ row.name }}</strong>
            <div class="meta">{{ row.id }}</div>
          </template>
        </el-table-column>
        <el-table-column label="站点" prop="marketplace_id" width="160" show-overflow-tooltip />
        <el-table-column label="区域" prop="region" width="120" show-overflow-tooltip />
        <el-table-column label="授权状态" width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag :type="getShopStatusMeta(row.status).tagType">
              {{ getShopStatusMeta(row.status).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="参与同步" width="120" align="center" show-overflow-tooltip>
          <template #default="{ row }">
            <el-switch
              v-model="row.sync_enabled"
              :disabled="row.status !== '0'"
              @change="(v) => toggleSync(row, normalizeSwitchValue(v))"
            />
          </template>
        </el-table-column>
      </el-table>

      <TablePaginationBar
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="rows.length"
        :page-sizes="[10, 20, 50]"
      />
    </el-card>

    <TaskProgress v-if="refreshTaskId" :task-id="refreshTaskId" @terminal="onRefreshDone" />
  </div>
</template>

<script setup lang="ts">
import { listShops, patchShop, refreshShops, type Shop } from '@/api/config'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import { normalizeSwitchValue } from '@/utils/element'
import { getShopStatusMeta } from '@/utils/status'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

const rows = ref<Shop[]>([])
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
    rows.value = await listShops()
  } finally {
    loading.value = false
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

async function toggleSync(row: Shop, value: boolean): Promise<void> {
  try {
    await patchShop(row.id, value)
    ElMessage.success(`${row.name} 已${value ? '启用' : '禁用'}同步。`)
  } catch {
    row.sync_enabled = !value
    ElMessage.error('更新失败。')
  }
}

onMounted(reload)
</script>

<style lang="scss" scoped>
.shop-view {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-4;
}

.card-title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}

.card-meta,
.meta {
  color: $color-text-secondary;
  font-size: $font-size-xs;
}

.card-meta {
  margin-top: 4px;
}

@media (max-width: 900px) {
  .card-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
