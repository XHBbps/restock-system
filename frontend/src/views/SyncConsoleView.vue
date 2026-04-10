<template>
  <div class="sync-console-view">
    <DashboardPageHeader
      eyebrow="Operations"
      title="数据同步"
      description="自动同步与手动同步统一在本页管理。顶部控制调度器，中部查看任务卡片，底部查看状态与失败调用。"
    >
      <template #meta>
        <el-tag :type="schedulerStatus?.enabled ? 'success' : 'warning'">
          {{ schedulerStatus?.enabled ? '调度器已开启' : '调度器已关闭' }}
        </el-tag>
      </template>
      <template #actions>
        <el-button @click="reloadAll">刷新全部</el-button>
      </template>
    </DashboardPageHeader>

    <el-alert
      v-if="overview && overview.postal_compliance_warning > 0"
      type="warning"
      :closable="false"
      :title="`还有 ${overview.postal_compliance_warning} 个订单超过 50 天仍未拉取详情，已接近 60 天可见窗口。`"
    />

    <section class="stats-grid">
      <DashboardStatCard
        title="自动任务数"
        :value="autoSyncDefinitions.length"
        hint="调度器统一托管的自动同步任务"
      />
      <DashboardStatCard
        title="手动任务数"
        :value="manualSyncActions.length"
        hint="可人工触发的同步任务"
      />
      <DashboardStatCard
        title="失败同步任务"
        :value="failedSyncCount"
        :trend="failedSyncCount > 0 ? '建议优先排查' : '状态正常'"
        :trend-type="failedSyncCount > 0 ? 'negative' : 'positive'"
        hint="按最近一次执行状态统计"
      />
      <DashboardStatCard
        title="失败接口调用"
        :value="failedCallCount"
        hint="最近 24 小时累计失败调用"
      />
    </section>

    <section class="chart-grid">
      <DashboardChartCard
        title="同步任务状态分布"
        description="查看当前同步面板最近一次执行结果的整体分布。"
        :option="syncStatusChartOption"
        :empty="syncState.length === 0"
        empty-text="暂无同步状态数据"
      />
      <DashboardChartCard
        title="自动同步下次执行"
        description="展示调度器当前登记的自动任务，按下次执行时间排序。"
        :option="nextRunChartOption"
        :empty="autoScheduleRows.length === 0"
        empty-text="暂无自动调度任务"
      />
    </section>

    <DataTableCard title="调度器控制" description="控制自动同步总开关，并查看当前计划参数。">
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

    <DashboardSection title="自动同步任务" description="自动同步任务由调度器统一托管，桌面端最多每行展示 3 张卡片。">
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

    <DashboardSection title="手动同步任务" description="全量同步单独一行，其余任务按 3 列卡片展示。">
      <div class="manual-section">
        <SyncTaskHeroCard
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

    <section class="bottom-grid">
      <DataTableCard title="同步任务状态" description="统一查看各同步任务最近一次执行结果。">
        <SyncStateTable :rows="pagedSyncState" :job-label-map="syncJobLabelMap" />
        <template #pagination>
          <TablePaginationBar
            v-model:current-page="syncStatePage"
            v-model:page-size="syncStatePageSize"
            :total="syncState.length"
          />
        </template>
      </DataTableCard>

      <DataTableCard title="最近失败调用" description="用于排查外部接口失败并直接重试。">
        <template #toolbar>
          <el-switch v-model="onlyFailed" active-text="仅失败" @change="loadRecentCalls" />
        </template>
        <FailedApiCallTable :rows="pagedRecentCalls" @retry="retry" />
        <template #pagination>
          <TablePaginationBar
            v-model:current-page="recentPage"
            v-model:page-size="recentPageSize"
            :total="recentCalls.length"
          />
        </template>
      </DataTableCard>
    </section>

    <TaskProgress v-if="currentTaskId" :task-id="currentTaskId" @terminal="onTaskDone" />
  </div>
</template>

<script setup lang="ts">
import client from '@/api/client'
import { listSyncState, type SyncStateRow } from '@/api/data'
import {
  getApiCallsOverview,
  getRecentCalls,
  retryCall,
  type ApiCallsOverview,
  type RecentCall,
} from '@/api/monitor'
import { getSchedulerStatus, setSchedulerStatus, type SchedulerStatus } from '@/api/sync'
import type { TaskRun } from '@/api/task'
import DataTableCard from '@/components/dashboard/DataTableCard.vue'
import DashboardChartCard from '@/components/dashboard/DashboardChartCard.vue'
import DashboardPageHeader from '@/components/dashboard/DashboardPageHeader.vue'
import DashboardSection from '@/components/dashboard/DashboardSection.vue'
import DashboardStatCard from '@/components/dashboard/DashboardStatCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import FailedApiCallTable from '@/components/sync/FailedApiCallTable.vue'
import SchedulerControlPanel from '@/components/sync/SchedulerControlPanel.vue'
import SyncStateTable from '@/components/sync/SyncStateTable.vue'
import SyncTaskCard from '@/components/sync/SyncTaskCard.vue'
import SyncTaskHeroCard from '@/components/sync/SyncTaskHeroCard.vue'
import {
  autoSyncDefinitions,
  manualSyncActions,
  syncJobLabelMap,
  type SyncActionDefinition,
} from '@/config/sync'
import { getActionErrorMessage } from '@/utils/apiError'
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
const overview = ref<ApiCallsOverview | null>(null)
const recentCalls = ref<RecentCall[]>([])
const onlyFailed = ref(true)
const currentTaskId = ref<number | null>(null)
const loadingActions = reactive<Record<string, boolean>>({})

const syncStatePage = ref(1)
const syncStatePageSize = ref(10)
const recentPage = ref(1)
const recentPageSize = ref(10)

const failedSyncCount = computed(() => syncState.value.filter((item) => item.last_status === 'failed').length)
const failedCallCount = computed(() =>
  (overview.value?.endpoints || []).reduce((sum, endpoint) => sum + endpoint.failed_count, 0),
)

function formatTime(value?: string | null): string {
  return value ? dayjs(value).format('MM-DD HH:mm:ss') : '暂无记录'
}

function getActionMeta(action: SyncActionDefinition) {
  const row = syncState.value.find((item) => item.job_name === action.jobName)
  return {
    statusMeta: getSyncStatusMeta(row?.last_status),
    lastRunAt: formatTime(row?.last_run_at),
    lastSuccessAt: formatTime(row?.last_success_at),
    lastError: row?.last_error || '',
  }
}

const heroAction = computed(() => {
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
      lastRunAt: formatTime(stateRow?.last_run_at),
      lastSuccessAt: formatTime(stateRow?.last_success_at),
      lastError: stateRow?.last_error || '',
      nextRunAt: formatTime(scheduledJob?.next_run_time),
    }
  }),
)

const autoScheduleRows = computed(() =>
  [...(schedulerStatus.value?.jobs || [])]
    .filter((item) => item.next_run_time)
    .sort((a, b) => dayjs(a.next_run_time).valueOf() - dayjs(b.next_run_time).valueOf())
    .slice(0, 8),
)

const pagedSyncState = computed(() => {
  const start = (syncStatePage.value - 1) * syncStatePageSize.value
  return syncState.value.slice(start, start + syncStatePageSize.value)
})

const pagedRecentCalls = computed(() => {
  const start = (recentPage.value - 1) * recentPageSize.value
  return recentCalls.value.slice(start, start + recentPageSize.value)
})

const syncStatusChartOption = computed<EChartsCoreOption>(() => {
  const counts = syncState.value.reduce<Record<string, number>>((acc, item) => {
    const key = item.last_status || 'idle'
    acc[key] = (acc[key] || 0) + 1
    return acc
  }, {})
  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, icon: 'circle', textStyle: { color: '#71717a' } },
    series: [
      {
        type: 'pie',
        radius: ['52%', '78%'],
        itemStyle: { borderColor: '#ffffff', borderWidth: 4 },
        label: { formatter: '{b}\n{c}', color: '#09090b', fontSize: 12 },
        data: [
          { name: '成功', value: (counts.success || 0) + (counts.completed || 0), itemStyle: { color: '#16a34a' } },
          { name: '失败', value: counts.failed || 0, itemStyle: { color: '#dc2626' } },
          { name: '执行中', value: counts.running || 0, itemStyle: { color: '#d97706' } },
          { name: '未执行', value: counts.idle || 0, itemStyle: { color: '#a1a1aa' } },
        ].filter((item) => item.value > 0),
      },
    ],
  }
})

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
      data: autoScheduleRows.value.map((item) =>
        Math.max(dayjs(item.next_run_time).diff(dayjs(), 'minute'), 0),
      ),
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

async function loadOverview(): Promise<void> {
  overview.value = await getApiCallsOverview(24)
}

async function loadRecentCalls(): Promise<void> {
  recentPage.value = 1
  recentCalls.value = await getRecentCalls({ only_failed: onlyFailed.value, limit: 200 })
}

async function reloadAll(): Promise<void> {
  await Promise.allSettled([loadScheduler(), loadSyncState(), loadOverview(), loadRecentCalls()])
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

async function retry(id: number): Promise<void> {
  try {
    const resp = await retryCall(id)
    if (resp.task_id) {
      currentTaskId.value = resp.task_id
      ElMessage.success('重试任务已入队。')
      return
    }
    ElMessage.warning('该调用暂不支持自动重试。')
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '重试失败。'))
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: $space-4;
}

.chart-grid,
.bottom-grid {
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
  .stats-grid,
  .task-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .stats-grid,
  .chart-grid,
  .bottom-grid,
  .task-grid {
    grid-template-columns: 1fr;
  }
}
</style>
