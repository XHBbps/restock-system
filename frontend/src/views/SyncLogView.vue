<template>
  <div class="sync-log-view">
    <section class="top-grid">
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

    <DashboardChartCard
      title="同步任务状态分布"
      description="查看当前同步面板最近一次执行结果的整体分布。"
      :option="syncStatusChartOption"
      :empty="syncStatusChartData.length === 0"
      empty-text="暂无同步状态数据"
    />

    <DataTableCard title="同步任务状态" description="统一查看各同步任务最近一次执行结果。">
      <template #toolbar>
        <el-button @click="loadSyncState">刷新</el-button>
      </template>
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

    <TaskProgress v-if="currentTaskId" :task-id="currentTaskId" @terminal="onTaskDone" />
  </div>
</template>

<script setup lang="ts">
import { listSyncState, type SyncStateRow } from '@/api/data'
import {
  getApiCallsOverview,
  getRecentCalls,
  retryCall,
  type ApiCallsOverview,
  type RecentCall,
} from '@/api/monitor'
import type { TaskRun } from '@/api/task'
import DataTableCard from '@/components/dashboard/DataTableCard.vue'
import DashboardChartCard from '@/components/dashboard/DashboardChartCard.vue'
import DashboardStatCard from '@/components/dashboard/DashboardStatCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import FailedApiCallTable from '@/components/sync/FailedApiCallTable.vue'
import SyncStateTable from '@/components/sync/SyncStateTable.vue'
import { syncJobLabelMap } from '@/config/sync'
import { getActionErrorMessage } from '@/utils/apiError'
import type { EChartsCoreOption } from 'echarts/core'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

type SyncChartDatum = {
  name: string
  value: number
  color: string
}

const syncState = ref<SyncStateRow[]>([])
const overview = ref<ApiCallsOverview | null>(null)
const recentCalls = ref<RecentCall[]>([])
const onlyFailed = ref(true)
const currentTaskId = ref<number | null>(null)

const syncStatePage = ref(1)
const syncStatePageSize = ref(10)
const recentPage = ref(1)
const recentPageSize = ref(10)

const failedSyncCount = computed(() => syncState.value.filter((row) => row.last_status === 'failed').length)
const failedCallCount = computed(() =>
  (overview.value?.endpoints || []).reduce((sum, endpoint) => sum + endpoint.failed_count, 0),
)

const pagedSyncState = computed(() => {
  const start = (syncStatePage.value - 1) * syncStatePageSize.value
  return syncState.value.slice(start, start + syncStatePageSize.value)
})

const pagedRecentCalls = computed(() => {
  const start = (recentPage.value - 1) * recentPageSize.value
  return recentCalls.value.slice(start, start + recentPageSize.value)
})

const syncStatusChartData = computed<SyncChartDatum[]>(() => {
  const counts = syncState.value.reduce<Record<string, number>>((acc, item) => {
    const key = item.last_status || 'idle'
    acc[key] = (acc[key] || 0) + 1
    return acc
  }, {})
  return [
    { name: '成功', value: (counts.success || 0) + (counts.completed || 0), color: '#16a34a' },
    { name: '失败', value: counts.failed || 0, color: '#dc2626' },
    { name: '执行中', value: counts.running || 0, color: '#d97706' },
    { name: '未执行', value: counts.idle || 0, color: '#a1a1aa' },
  ].filter((item) => item.value > 0)
})

const syncStatusChartOption = computed<EChartsCoreOption>(() => {
  return {
    tooltip: {
      trigger: 'item',
      formatter(params: unknown) {
        const item = params as { name?: string; value?: number; percent?: number }
        return [
          `<div>${item.name ?? '-'}</div>`,
          `<div>数量：${item.value ?? 0}</div>`,
          `<div>占比：${item.percent ?? 0}%</div>`,
        ].join('')
      },
    },
    legend: {
      bottom: 8,
      icon: 'circle',
      textStyle: { color: '#71717a' },
    },
    series: [
      {
        type: 'pie',
        radius: ['46%', '72%'],
        center: ['50%', '38%'],
        itemStyle: { borderColor: '#ffffff', borderWidth: 4 },
        label: {
          color: '#09090b',
          fontSize: 12,
          formatter: '{b}\n{c}',
        },
        data: syncStatusChartData.value.map((item) => ({
          name: item.name,
          value: item.value,
          itemStyle: { color: item.color },
        })),
      },
    ],
  }
})

async function loadSyncState(): Promise<void> {
  try {
    syncState.value = await listSyncState()
  } catch (e) {
    ElMessage.error(getActionErrorMessage(e, '加载同步状态'))
  }
}

async function loadOverview(): Promise<void> {
  try {
    overview.value = await getApiCallsOverview(24)
  } catch (e) {
    ElMessage.error(getActionErrorMessage(e, '加载 API 调用概览'))
  }
}

async function loadRecentCalls(): Promise<void> {
  try {
    recentPage.value = 1
    recentCalls.value = await getRecentCalls({ only_failed: onlyFailed.value, limit: 200 })
  } catch (e) {
    ElMessage.error(getActionErrorMessage(e, '加载最近调用记录'))
  }
}

async function reloadAll(): Promise<void> {
  await Promise.allSettled([loadSyncState(), loadOverview(), loadRecentCalls()])
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
  ElMessage.error(task.error_msg || '任务执行失败。')
}

onMounted(reloadAll)
</script>

<style lang="scss" scoped>
.sync-log-view {
  display: flex;
  flex-direction: column;
  gap: $space-6;
}

.top-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: $space-4;
}

@media (max-width: 900px) {
  .top-grid {
    grid-template-columns: 1fr;
  }
}
</style>
