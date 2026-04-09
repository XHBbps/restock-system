<template>
  <div class="replenishment-run-view">
    <DashboardPageHeader
      eyebrow="Engine"
      title="补货触发"
    >
      <template #actions>
        <el-button @click="load">刷新摘要</el-button>
        <el-button type="primary" :loading="running" @click="trigger">生成补货建议</el-button>
      </template>
    </DashboardPageHeader>

    <section class="stats-grid">
      <DashboardStatCard title="当前建议单" :value="suggestion ? `#${suggestion.id}` : '-'" />
      <DashboardStatCard title="建议状态" :value="statusMeta.label" />
      <DashboardStatCard title="建议条目数" :value="suggestion?.total_items ?? 0" />
      <DashboardStatCard
        title="已推送条目"
        :value="suggestion?.pushed_items ?? 0"
      />
    </section>

    <section class="content-grid">
      <DashboardChartCard
        title="国家采购分布"
        :option="countryChartOption"
        :empty="countryRows.length === 0"
        empty-text="当前没有可展示的国家分布"
      />
      <DataTableCard title="当前建议摘要">
        <div v-if="suggestion" class="summary-list">
          <div class="summary-row">
            <span>建议单编号</span>
            <strong>#{{ suggestion.id }}</strong>
          </div>
          <div class="summary-row">
            <span>状态</span>
            <el-tag :type="statusMeta.tagType">{{ statusMeta.label }}</el-tag>
          </div>
          <div class="summary-row">
            <span>生成时间</span>
            <strong>{{ formatTime(suggestion.created_at) }}</strong>
          </div>
          <div class="summary-row">
            <span>条目数</span>
            <strong>{{ suggestion.total_items }}</strong>
          </div>
          <div class="summary-actions">
            <el-button link type="primary" @click="goCurrent">查看当前建议</el-button>
            <el-button link @click="goHistory">查看历史记录</el-button>
          </div>
        </div>
        <el-empty v-else description="当前没有活动建议单" :image-size="72" />
      </DataTableCard>
    </section>

    <TaskProgress v-if="currentTaskId" :task-id="currentTaskId" @terminal="onTaskDone" />
  </div>
</template>

<script setup lang="ts">
import client from '@/api/client'
import type { TaskRun } from '@/api/task'
import { getCurrentSuggestion, type SuggestionDetail } from '@/api/suggestion'
import DashboardChartCard from '@/components/dashboard/DashboardChartCard.vue'
import DashboardPageHeader from '@/components/dashboard/DashboardPageHeader.vue'
import DashboardStatCard from '@/components/dashboard/DashboardStatCard.vue'
import DataTableCard from '@/components/dashboard/DataTableCard.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { getSuggestionStatusMeta } from '@/utils/status'
import type { EChartsCoreOption } from 'echarts/core'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const suggestion = ref<SuggestionDetail | null>(null)
const running = ref(false)
const currentTaskId = ref<number | null>(null)

const statusMeta = computed(() =>
  suggestion.value ? getSuggestionStatusMeta(suggestion.value.status) : { label: '暂无', tagType: 'info' as const },
)

const countryRows = computed(() => {
  const aggregate = new Map<string, number>()
  for (const item of suggestion.value?.items || []) {
    for (const [country, qty] of Object.entries(item.country_breakdown || {})) {
      aggregate.set(country, (aggregate.get(country) || 0) + qty)
    }
  }
  return [...aggregate.entries()]
    .map(([country, qty]) => ({ country, qty }))
    .sort((a, b) => b.qty - a.qty)
    .slice(0, 10)
})

const countryChartOption = computed<EChartsCoreOption>(() => ({
  grid: { left: 24, right: 24, top: 24, bottom: 24, containLabel: true },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: {
    type: 'category',
    data: countryRows.value.map((item) => item.country),
    axisLabel: { color: '#71717a' },
    axisTick: { show: false },
  },
  yAxis: {
    type: 'value',
    axisLabel: { color: '#71717a' },
    splitLine: { lineStyle: { color: '#f4f4f5' } },
  },
  series: [
    {
      type: 'bar',
      data: countryRows.value.map((item) => item.qty),
      barWidth: 18,
      itemStyle: { color: '#18181b', borderRadius: [6, 6, 0, 0] },
    },
  ],
}))

function formatTime(value: string): string {
  return dayjs(value).format('YYYY-MM-DD HH:mm:ss')
}

async function load(): Promise<void> {
  try {
    suggestion.value = await getCurrentSuggestion()
  } catch {
    suggestion.value = null
  }
}

async function trigger(): Promise<void> {
  running.value = true
  try {
    const { data } = await client.post<{ task_id: number; existing?: boolean }>('/api/engine/run')
    currentTaskId.value = data.task_id
    if (data.existing) {
      ElMessage.warning('已有规则引擎任务在运行，当前复用现有任务进度。')
    } else {
      ElMessage.success('规则引擎任务已入队。')
    }
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '补货任务触发失败。'))
  } finally {
    running.value = false
  }
}

async function onTaskDone(task: TaskRun): Promise<void> {
  currentTaskId.value = null
  await load()
  if (task.status === 'success') {
    ElMessage.success('补货任务已完成，当前建议摘要已刷新。')
    return
  }
  ElMessage.error(task.error_msg || '补货任务执行失败，请查看任务详情。')
}

function goCurrent(): void {
  router.push('/replenishment/current')
}

function goHistory(): void {
  router.push('/replenishment/history')
}

onMounted(load)
</script>

<style lang="scss" scoped>
.replenishment-run-view {
  display: flex;
  flex-direction: column;
  gap: $space-6;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: $space-4;
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: $space-4;
}

.summary-list {
  display: flex;
  flex-direction: column;
  gap: $space-3;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-4;
}

.summary-actions {
  display: flex;
  gap: $space-3;
  flex-wrap: wrap;
}

@media (max-width: 1280px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .stats-grid,
  .content-grid {
    grid-template-columns: 1fr;
  }
}
</style>
