<template>
  <div class="shop-view">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="card-title">店铺管理</span>
          <el-button :loading="refreshing" @click="refresh">
            手动刷新（拉取赛狐）
          </el-button>
        </div>
      </template>

      <el-table :data="rows" v-loading="loading">
        <el-table-column label="店铺" min-width="200">
          <template #default="{ row }">
            <strong>{{ row.name }}</strong>
            <div class="meta">{{ row.id }}</div>
          </template>
        </el-table-column>
        <el-table-column label="站点" prop="marketplace_id" width="160" />
        <el-table-column label="区域" prop="region" width="100" />
        <el-table-column label="授权状态" width="140">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="参与同步" width="120" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.sync_enabled"
              :disabled="row.status !== '0'"
              @change="(v: boolean) => toggleSync(row, v)"
            />
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <TaskProgress v-if="refreshTaskId" :task-id="refreshTaskId" @terminal="onRefreshDone" />
  </div>
</template>

<script setup lang="ts">
import { listShops, patchShop, refreshShops, type Shop } from '@/api/config'
import TaskProgress from '@/components/TaskProgress.vue'
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

const rows = ref<Shop[]>([])
const loading = ref(false)
const refreshing = ref(false)
const refreshTaskId = ref<number | null>(null)

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
    ElMessage.error('刷新失败')
  } finally {
    refreshing.value = false
  }
}

async function onRefreshDone(): Promise<void> {
  refreshTaskId.value = null
  await reload()
  ElMessage.success('店铺列表已更新')
}

async function toggleSync(row: Shop, v: boolean): Promise<void> {
  try {
    await patchShop(row.id, v)
    ElMessage.success(`${row.name} 同步已${v ? '启用' : '禁用'}`)
  } catch {
    row.sync_enabled = !v
    ElMessage.error('更新失败')
  }
}

function statusTagType(s: string): string {
  return ({ '0': 'success', '1': 'danger', '2': 'warning' } as Record<string, string>)[s] || 'info'
}

function statusLabel(s: string): string {
  return (
    { '0': '正常', '1': '授权失效', '2': 'SP 授权失效' } as Record<string, string>
  )[s] || s
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
}
.card-title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}
.meta {
  color: $color-text-secondary;
  font-size: $font-size-xs;
  margin-top: 2px;
}
</style>
