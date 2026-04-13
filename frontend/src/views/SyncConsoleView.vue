<template>
  <div class="sync-console-view">
    <DashboardPageHeader title="数据同步">
      <template #meta>
        <el-tag :type="schedulerStatus?.enabled ? 'success' : 'warning'">
          {{ schedulerStatus?.enabled ? '调度器已开启' : '调度器已关闭' }}
        </el-tag>
      </template>
      <template #actions>
        <el-button @click="reloadAll">刷新全部</el-button>
      </template>
    </DashboardPageHeader>

    <section class="stats-grid-2">
      <DashboardStatCard
        title="自动任务数"
        :value="autoSyncDefinitions.length"
        hint="由调度器统一托管的自动同步任务"
      />
      <DashboardStatCard title="手动任务数" :value="manualSyncActions.length" hint="可人工触发的同步任务" />
    </section>

    <DashboardChartCard
      title="自动同步下次执行"
      :option="nextRunChartOption"
      :empty="autoScheduleRows.length === 0"
      empty-text="暂无自动调度任务"
    />

    <DataTableCard title="调度器控制">
      <template #toolbar>
        <el-button :loading="schedulerLoading" @click="loadScheduler">刷新状态</el-button>
      </template>
      <SchedulerControlPanel
        :status="schedulerStatus"
        :refreshing="schedulerLoading"
        :toggle-loading="schedulerToggleLoading"
        @refresh="loadScheduler"
        @toggle="toggleScheduler"
      />
    </DataTableCard>

    <DashboardSection title="自动同步任务">
      <div class="task-grid">
        <SyncTaskCard
          v-for="job in autoJobCards"
          :key="job.jobName"
          :title="job.label"
          :status-meta="job.statusMeta"
          :last-run-at="job.lastRunAt"
          :last-success-at="job.lastSuccessAt"
          :last-error="job.lastError"
          :footer-hint="`执行建议：${job.cadence} 当前计划：${job.nextRunAt}`"
        >
          <template #actions>
            <span class="readonly-hint">自动任务由调度器执行</span>
          </template>
        </SyncTaskCard>
      </div>
    </DashboardSection>

    <DashboardSection title="手动同步任务">
      <div class="manual-section">
        <SyncTaskHeroCard
          v-if="heroAction"
          :title="heroAction.action.label"
          :status-meta="heroAction.statusMeta"
          :last-run-at="heroAction.lastRunAt"
          :last-success-at="heroAction.lastSuccessAt"
          :last-error="heroAction.lastError"
          :loading="loadingActions[heroAction.action.key] || false"
          @run="trigger(heroAction.action)"
        />

        <div class="task-grid">
          <SyncTaskCard
            v-for="action in normalManualActions"
            :key="action.action.key"
            :title="action.action.label"
            :status-meta="action.statusMeta"
            :last-run-at="action.lastRunAt"
            :last-success-at="action.lastSuccessAt"
            :last-error="action.lastError"
            :loading="loadingActions[action.action.key] || false"
            @run="trigger(action.action)"
          />
        </div>
      </div>
    </DashboardSection>
    <TaskProgress v-if="currentTaskId" :task-id="currentTaskId" @terminal="onTaskDone" />
  </div>
</template>

<script setup lang="ts">
import { listSyncState, type SyncStateRow } from '@/api/data'
import { getSchedulerStatus, setSchedulerStatus, type SchedulerStatus } from '@/api/sync'
import type { TaskRun } from '@/api/task'
import DashboardChartCard from '@/components/dashboard/DashboardChartCard.vue'
import DashboardPageHeader from '@/components/dashboard/DashboardPageHeader.vue'
import DashboardSection from '@/components/dashboard/DashboardSection.vue'
import DashboardStatCard from '@/components/dashboard/DashboardStatCard.vue'
import DataTableCard from '@/components/dashboard/DataTableCard.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import SchedulerControlPanel from '@/components/sync/SchedulerControlPanel.vue'
import SyncTaskCard from '@/components/sync/SyncTaskCard.vue'
import SyncTaskHeroCard from '@/components/sync/SyncTaskHeroCard.vue'
import { autoSyncDefinitions, manualSyncActions, type SyncActionDefinition, syncJobLabelMap } from '@/config/sync'
import client from '@/api/client'
import { getActionErrorMessage } from '@/utils/apiError'
import { formatDetailTime } from '@/utils/format'
import { getSyncStatusMeta } from '@/utils/status'
import type { EChartsCoreOption } from 'echarts/core'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

interface ActionCardViewModel {
  action: SyncActionDefinition
  statusMeta: ReturnType<typeof getSyncStatusMeta>
  lastRunAt: string
  lastSuccessAt: string
  lastError: string
}

const schedulerStatus = ref<SchedulerStatus | null>(null)
const schedulerLoading = ref(false)
const schedulerToggleLoading = ref(false)
const syncState = ref<SyncStateRow[]>([])
const currentTaskId = ref<number | null>(null)
const loadingActions = reactive<Record<string, boolean>>({})

function getActionMeta(action: SyncActionDefinition) {
  const row = syncState.value.find((item) => item.job_name === action.jobName)
  return {
    statusMeta: getSyncStatusMeta(row?.last_status),
    lastRunAt: formatDetailTime(row?.last_run_at),
    lastSuccessAt: formatDetailTime(row?.last_success_at),
    lastError: row?.last_error || '',
  }
}

const heroAction = computed(() => {
  if (manualSyncActions.length === 0) return null
  const action = manualSyncActions[0]
  return {
    action,
    ...getActionMeta(action),
  }
})

const normalManualActions = computed<ActionCardViewModel[]>(() =>
  manualSyncActions.slice(1).map((action) => ({
    action,
    ...getActionMeta(action),
  })),
)

const autoJobCards = computed(() =>
  autoSyncDefinitions.map((definition) => {
    const stateRow = syncState.value.find((item) => item.job_name === definition.jobName)
    const scheduledJob = schedulerStatus.value?.jobs.find((item) => item.job_name === definition.jobName)
    return {
      ...definition,
      statusMeta: getSyncStatusMeta(stateRow?.last_status),
      lastRunAt: formatDetailTime(stateRow?.last_run_at),
      lastSuccessAt: formatDetailTime(stateRow?.last_success_at),
      lastError: stateRow?.last_error || '',
      nextRunAt: formatDetailTime(scheduledJob?.next_run_time),
    }
  }),
)

const autoScheduleRows = computed(() =>
  [...(schedulerStatus.value?.jobs || [])]
    .filter((item) => item.next_run_time)
    .sort((a, b) => dayjs(a.next_run_time).valueOf() - dayjs(b.next_run_time).valueOf())
    .slice(0, 8),
)

const nextRunChartOption = computed<EChartsCoreOption>(() => ({
  grid: { left: 24, right: 24, top: 24, bottom: 24, containLabel: true },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: {
    type: 'value',
    axisLabel: { color: '#71717a' },
    splitLine: { lineStyle: { color: '#f4f4f5' } },
  },
  yAxis: {
    type: 'category',
    data: autoScheduleRows.value.map((item) => syncJobLabelMap[item.job_name] || item.job_name),
    axisLabel: { color: '#71717a', width: 180, overflow: 'truncate' },
    axisTick: { show: false },
  },
  series: [
    {
      type: 'bar',
      data: autoScheduleRows.value.map((item) => Math.max(dayjs(item.next_run_time).diff(dayjs(), 'minute'), 0)),
      barWidth: 16,
      itemStyle: { color: '#18181b', borderRadius: [0, 6, 6, 0] },
    },
  ],
}))

async function loadScheduler(): Promise<void> {
  schedulerLoading.value = true
  try {
    schedulerStatus.value = await getSchedulerStatus()
  } finally {
    schedulerLoading.value = false
  }
}

async function toggleScheduler(enabled: boolean): Promise<void> {
  schedulerToggleLoading.value = true
  try {
    schedulerStatus.value = await setSchedulerStatus(enabled)
    ElMessage.success(enabled ? '调度器已开启。' : '调度器已关闭。')
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '调度器切换失败。'))
    await loadScheduler()
  } finally {
    schedulerToggleLoading.value = false
  }
}

async function loadSyncState(): Promise<void> {
  syncState.value = await listSyncState()
}

async function reloadAll(): Promise<void> {
  await Promise.allSettled([loadScheduler(), loadSyncState()])
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
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '同步任务触发失败。'))
  } finally {
    loadingActions[action.key] = false
  }
}

async function onTaskDone(task: TaskRun): Promise<void> {
  currentTaskId.value = null
  await reloadAll()
  if (task.status === 'success') {
    ElMessage.success('任务已完成，页面状态已刷新。')
    return
  }
  ElMessage.error(task.error_msg || '任务执行失败，请查看同步状态与失败明细。')
}

onMounted(reloadAll)
</script>

<style lang="scss" scoped>
.sync-console-view {
  display: flex;
  flex-direction: column;
  gap: $space-6;
}

.stats-grid-2 {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: $space-4;
}

.task-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: $space-4;
}

.manual-section {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.readonly-hint {
  color: $color-text-secondary;
  font-size: $font-size-xs;
}

@media (max-width: 1280px) {
  .task-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .stats-grid-2,
  .task-grid {
    grid-template-columns: 1fr;
  }
}
</style>
