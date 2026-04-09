<template>
  <div class="sync-manual-view">
    <section class="intro-card">
      <div>
        <h1 class="page-title">手动同步</h1>
      </div>
      <el-button @click="reload">刷新状态</el-button>
    </section>

    <section class="card-grid">
      <el-card
        v-for="action in manualSyncActions"
        :key="action.key"
        shadow="never"
        :class="{ 'card-emphasis': action.key === 'sync_all' }"
      >
        <div class="sync-card">
          <div class="sync-card__top">
            <div>
              <div class="sync-card__title">{{ action.label }}</div>
            </div>
            <el-tag :type="getActionMeta(action).status.tagType">
              {{ getActionMeta(action).status.label }}
            </el-tag>
          </div>

          <div class="sync-card__meta">
            <div>最近运行：{{ getActionMeta(action).lastRunAt }}</div>
            <div>最近成功：{{ getActionMeta(action).lastSuccessAt }}</div>
            <div v-if="getActionMeta(action).lastError" class="sync-card__error">
              最近错误：{{ getActionMeta(action).lastError }}
            </div>
          </div>

          <div class="sync-card__actions">
            <el-button
              type="primary"
              :loading="loadingActions[action.key] || false"
              @click="trigger(action)"
            >
              {{ action.key === 'sync_all' ? '执行全量同步' : '执行同步' }}
            </el-button>
          </div>
        </div>
      </el-card>
    </section>

    <TaskProgress v-if="currentTaskId" :task-id="currentTaskId" @terminal="onTaskDone" />
  </div>
</template>

<script setup lang="ts">
import client from '@/api/client'
import { listSyncState, type SyncStateRow } from '@/api/data'
import TaskProgress from '@/components/TaskProgress.vue'
import { manualSyncActions, type SyncActionDefinition } from '@/config/sync'
import { getSyncStatusMeta } from '@/utils/status'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

const syncState = ref<SyncStateRow[]>([])
const currentTaskId = ref<number | null>(null)
const loadingActions = reactive<Record<string, boolean>>({})

function formatTime(value?: string | null): string {
  return value ? dayjs(value).format('MM-DD HH:mm:ss') : '暂无记录'
}

function getActionMeta(action: SyncActionDefinition) {
  const row = syncState.value.find((item) => item.job_name === action.jobName)
  return {
    status: getSyncStatusMeta(row?.last_status),
    lastRunAt: formatTime(row?.last_run_at),
    lastSuccessAt: formatTime(row?.last_success_at),
    lastError: row?.last_error || '',
  }
}

async function reload(): Promise<void> {
  syncState.value = await listSyncState()
}

async function trigger(action: SyncActionDefinition): Promise<void> {
  loadingActions[action.key] = true
  try {
    const { data } = await client.post<{ task_id: number; existing?: boolean }>(action.url)
    currentTaskId.value = data.task_id
    if (data.existing) {
      ElMessage.warning('已有同名任务在运行，当前复用现有任务进度。')
    } else {
      ElMessage.success('同步任务已入队。')
    }
  } catch {
    ElMessage.error('同步任务触发失败。')
  } finally {
    loadingActions[action.key] = false
  }
}

async function onTaskDone(): Promise<void> {
  currentTaskId.value = null
  await reload()
  ElMessage.success('同步任务已结束，状态已刷新。')
}

onMounted(reload)
</script>

<style lang="scss" scoped>
.sync-manual-view {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.intro-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-4;
  padding: $space-5;
  border-radius: $radius-xl;
  border: 1px solid $color-border-default;
  background: $color-bg-card;
}

.page-title {
  margin: 0;
  font-size: 24px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: $space-4;
}

.card-emphasis {
  border-color: rgba(33, 95, 255, 0.3);
}

.sync-card {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.sync-card__top {
  display: flex;
  justify-content: space-between;
  gap: $space-4;
}

.sync-card__title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}

.sync-card__meta {
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.sync-card__meta {
  display: flex;
  flex-direction: column;
  gap: $space-2;
}

.sync-card__error {
  color: $color-danger;
}

.sync-card__actions {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 900px) {
  .intro-card,
  .sync-card__top {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
