<template>
  <div class="api-monitor-view">
    <DashboardPageHeader
      eyebrow="Observability"
      title="接口监控"
      description="汇总最近 24 小时外部接口调用情况，支持查看调用规模、失败排行和失败明细，并可直接发起重试。"
    >
      <template #actions>
        <el-switch v-model="onlyFailed" active-text="仅看失败记录" @change="resetAndReload" />
        <el-button @click="reload">刷新监控</el-button>
      </template>
    </DashboardPageHeader>

    <section class="stats-grid">
      <DashboardStatCard title="接口数" :value="endpointRows.length" hint="最近 24 小时有调用记录的接口数量" />
      <DashboardStatCard title="总调用数" :value="totalCalls" hint="按接口聚合后的总调用次数" />
      <DashboardStatCard
        title="失败调用数"
        :value="failedCalls"
        :trend="failedCalls > 0 ? '需要排查' : '状态正常'"
        :trend-type="failedCalls > 0 ? 'negative' : 'positive'"
        hint="最近 24 小时累计失败调用次数"
      />
      <DashboardStatCard title="整体成功率" :value="`${successRate}%`" hint="成功调用数 / 总调用数" />
    </section>

    <section class="chart-grid">
      <DashboardChartCard
        title="接口调用量 Top 10"
        description="按最近 24 小时总调用量排序，快速识别高频接口。"
        :option="callCountChartOption"
        :empty="topCallRows.length === 0"
        empty-text="暂无接口调用数据"
      />
      <DashboardChartCard
        title="失败调用 Top 10"
        description="优先关注失败次数最高的接口。"
        :option="failedCountChartOption"
        :empty="failedRows.length === 0"
        empty-text="最近 24 小时没有失败接口"
      />
    </section>

    <section class="table-grid">
      <DataTableCard title="接口聚合" description="按接口维度查看调用规模、成功率和最近状态。">
        <el-table v-loading="loadingOverview" :data="pagedEndpointRows" table-layout="fixed" empty-text="暂无接口聚合数据" @sort-change="handleEndpointSortChange">
          <el-table-column label="接口名称" prop="endpoint" min-width="220" sortable="custom" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="endpoint-name">{{ row.endpoint }}</span>
            </template>
          </el-table-column>
          <el-table-column label="总调用数" prop="total_calls" width="110" align="right" sortable="custom" />
          <el-table-column label="成功数" prop="success_count" width="100" align="right" sortable="custom" />
          <el-table-column label="失败数" prop="failed_count" width="100" align="right" sortable="custom" />
          <el-table-column label="成功率" prop="success_rate" width="120" align="right" sortable="custom">
            <template #default="{ row }">{{ `${(row.success_rate * 100).toFixed(1)}%` }}</template>
          </el-table-column>
          <el-table-column label="最近调用时间" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">{{ formatDetailTime(row.last_called_at) }}</template>
          </el-table-column>
          <el-table-column label="最近错误" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">{{ row.last_error || '-' }}</template>
          </el-table-column>
        </el-table>

        <template #pagination>
          <TablePaginationBar
            v-model:current-page="endpointPage"
            v-model:page-size="endpointPageSize"
            :total="endpointRows.length"
          />
        </template>
      </DataTableCard>

      <DataTableCard :title="onlyFailed ? '失败调用明细' : '最近调用明细'" description="支持从失败记录直接发起重试。">
        <el-table v-loading="loadingRecent" :data="pagedRecentCalls" table-layout="fixed" empty-text="暂无调用明细">
          <el-table-column label="调用时间" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">{{ formatDetailTime(row.called_at) }}</template>
          </el-table-column>
          <el-table-column label="接口名称" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="endpoint-name">{{ row.endpoint }}</span>
            </template>
          </el-table-column>
          <el-table-column label="耗时(ms)" width="100" align="right">
            <template #default="{ row }">{{ formatDuration(row.duration_ms) }}</template>
          </el-table-column>
          <el-table-column label="HTTP 状态" width="100" align="center">
            <template #default="{ row }">{{ row.http_status ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="外部返回码" width="120" align="center">
            <template #default="{ row }">{{ row.saihu_code ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="错误信息" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">{{ row.saihu_msg || row.error_type || '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-button v-if="row.saihu_code !== 0" link type="primary" @click="retry(row.id)">
                重试
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <template #pagination>
          <TablePaginationBar v-model:current-page="page" v-model:page-size="pageSize" :total="recentCalls.length" />
        </template>
      </DataTableCard>
    </section>

    <TaskProgress v-if="currentTaskId" :task-id="currentTaskId" @terminal="onTaskDone" />
  </div>
</template>

<script setup lang="ts">
import {
  getApiCallsOverview,
  getRecentCalls,
  retryCall,
  type EndpointStats,
  type RecentCall,
} from '@/api/monitor'
import DashboardChartCard from '@/components/dashboard/DashboardChartCard.vue'
import DashboardPageHeader from '@/components/dashboard/DashboardPageHeader.vue'
import DashboardStatCard from '@/components/dashboard/DashboardStatCard.vue'
import DataTableCard from '@/components/dashboard/DataTableCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import type { TaskRun } from '@/api/task'
import { getTaskTerminalFeedback } from '@/utils/monitoring'
import { formatDetailTime, clampPage } from '@/utils/format'
import {
  applyLocalSort,
  compareNumber,
  compareText,
  normalizeSortOrder,
  type SortChangeEvent,
  type SortState,
} from '@/utils/tableSort'
import type { EChartsCoreOption } from 'echarts/core'
import { getActionErrorMessage } from '@/utils/apiError'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'

const endpointRows = ref<EndpointStats[]>([])
const recentCalls = ref<RecentCall[]>([])
const loadingOverview = ref(false)
const loadingRecent = ref(false)
const onlyFailed = ref(true)
const endpointPage = ref(1)
const endpointPageSize = ref(10)
const page = ref(1)
const pageSize = ref(10)
const currentTaskId = ref<number | null>(null)
const endpointSortState = ref<SortState>({})

const totalCalls = computed(() => endpointRows.value.reduce((sum, row) => sum + row.total_calls, 0))
const failedCalls = computed(() => endpointRows.value.reduce((sum, row) => sum + row.failed_count, 0))
const successRate = computed(() =>
  totalCalls.value ? (((totalCalls.value - failedCalls.value) / totalCalls.value) * 100).toFixed(1) : '0.0',
)

const sortedEndpointRows = computed(() =>
  applyLocalSort(
    endpointRows.value,
    endpointSortState.value,
    {
      endpoint: (left, right) => compareText(left.endpoint, right.endpoint),
      total_calls: (left, right) => compareNumber(left.total_calls, right.total_calls),
      success_count: (left, right) => compareNumber(left.success_count, right.success_count),
      failed_count: (left, right) => compareNumber(left.failed_count, right.failed_count),
      success_rate: (left, right) => compareNumber(left.success_rate, right.success_rate),
    },
  ),
)

const pagedEndpointRows = computed(() => {
  const start = (endpointPage.value - 1) * endpointPageSize.value
  return sortedEndpointRows.value.slice(start, start + endpointPageSize.value)
})

const pagedRecentCalls = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return recentCalls.value.slice(start, start + pageSize.value)
})

const topCallRows = computed(() => [...endpointRows.value].sort((a, b) => b.total_calls - a.total_calls).slice(0, 10))
const failedRows = computed(() =>
  [...endpointRows.value].filter((item) => item.failed_count > 0).sort((a, b) => b.failed_count - a.failed_count).slice(0, 10),
)

watch(
  [endpointRows, endpointPageSize],
  () => {
    endpointPage.value = clampPage(endpointPage.value, endpointRows.value.length, endpointPageSize.value)
  },
  { immediate: true },
)

watch(
  [recentCalls, pageSize],
  () => {
    page.value = clampPage(page.value, recentCalls.value.length, pageSize.value)
  },
  { immediate: true },
)

const callCountChartOption = computed<EChartsCoreOption>(() => ({
  grid: { left: 188, right: 20, top: 20, bottom: 12, containLabel: false },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    confine: true,
    formatter(params: unknown) {
      const point = (Array.isArray(params) ? params[0] : params) as { dataIndex?: number }
      const row = topCallRows.value[point.dataIndex ?? 0]
      if (!row) return ''

      return [
        `<div>${row.endpoint}</div>`,
        `<div>总调用数：${row.total_calls}</div>`,
        `<div>成功数：${row.success_count}</div>`,
        `<div>失败数：${row.failed_count}</div>`,
        `<div>成功率：${(row.success_rate * 100).toFixed(1)}%</div>`,
      ].join('')
    },
  },
  xAxis: {
    type: 'value',
    axisLabel: { color: '#71717a' },
    splitLine: { lineStyle: { color: '#f4f4f5' } },
  },
  yAxis: {
    type: 'category',
    data: topCallRows.value.map((item) => item.endpoint),
    axisLabel: {
      color: '#71717a',
      width: 150,
      overflow: 'truncate',
      lineHeight: 18,
    },
    axisTick: { show: false },
    axisLine: { show: false },
  },
  series: [
    {
      type: 'bar',
      data: topCallRows.value.map((item) => item.total_calls),
      barWidth: 16,
      itemStyle: { color: '#18181b', borderRadius: [0, 6, 6, 0] },
    },
  ],
}))

const failedCountChartOption = computed<EChartsCoreOption>(() => ({
  grid: { left: 188, right: 20, top: 20, bottom: 12, containLabel: false },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    confine: true,
    formatter(params: unknown) {
      const point = (Array.isArray(params) ? params[0] : params) as { dataIndex?: number }
      const row = failedRows.value[point.dataIndex ?? 0]
      if (!row) return ''

      return [
        `<div>${row.endpoint}</div>`,
        `<div>失败数：${row.failed_count}</div>`,
        `<div>总调用数：${row.total_calls}</div>`,
        `<div>最近错误：${row.last_error || '-'}</div>`,
      ].join('')
    },
  },
  xAxis: {
    type: 'value',
    axisLabel: { color: '#71717a' },
    splitLine: { lineStyle: { color: '#f4f4f5' } },
  },
  yAxis: {
    type: 'category',
    data: failedRows.value.map((item) => item.endpoint),
    axisLabel: {
      color: '#71717a',
      width: 150,
      overflow: 'truncate',
      lineHeight: 18,
    },
    axisTick: { show: false },
    axisLine: { show: false },
  },
  series: [
    {
      type: 'bar',
      data: failedRows.value.map((item) => item.failed_count),
      barWidth: 16,
      itemStyle: { color: '#dc2626', borderRadius: [0, 6, 6, 0] },
    },
  ],
}))

function formatDuration(value?: number | null): string {
  return typeof value === 'number' ? value.toFixed(0) : '-'
}

async function loadOverview(): Promise<void> {
  loadingOverview.value = true
  try {
    const overview = await getApiCallsOverview(24)
    endpointRows.value = overview.endpoints
  } finally {
    loadingOverview.value = false
  }
}

async function loadRecent(): Promise<void> {
  loadingRecent.value = true
  try {
    recentCalls.value = await getRecentCalls({ only_failed: onlyFailed.value, limit: 200 })
  } finally {
    loadingRecent.value = false
  }
}

async function reload(): Promise<void> {
  await Promise.all([loadOverview(), loadRecent()])
}

async function resetAndReload(): Promise<void> {
  page.value = 1
  await loadRecent()
}

function handleEndpointSortChange({ prop, order }: SortChangeEvent): void {
  const normalizedOrder = normalizeSortOrder(order)
  endpointSortState.value = normalizedOrder && prop ? { prop, order: normalizedOrder } : {}
  endpointPage.value = 1
}

async function retry(id: number): Promise<void> {
  try {
    const resp = await retryCall(id)
    if (resp.task_id) {
      currentTaskId.value = resp.task_id
      ElMessage.success('重试任务已入队')
      return
    }
    ElMessage.warning('该调用暂不支持自动重试')
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '重试触发失败'))
  }
}

async function onTaskDone(task: TaskRun): Promise<void> {
  currentTaskId.value = null
  await reload()
  const feedback = getTaskTerminalFeedback(task.status)
  ElMessage({
    type: feedback.type,
    message: feedback.message,
  })
}

onMounted(reload)
</script>

<style lang="scss" scoped>
.api-monitor-view {
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
.table-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: $space-4;
}

.endpoint-name {
  display: inline-block;
  max-width: 100%;
}

@media (max-width: 1280px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .stats-grid,
  .chart-grid,
  .table-grid {
    grid-template-columns: 1fr;
  }
}
</style>
