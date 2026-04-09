<template>
  <div class="workspace-view">
    <DashboardPageHeader
      eyebrow="Overview"
      title="工作台"
      description="这里汇总数据同步、补货建议和异常概况，帮助你先判断系统状态，再进入具体页面处理。"
    >
      <template #actions>
        <el-button type="primary" @click="go('/sync')">进入数据同步</el-button>
        <el-button @click="go('/replenishment/run')">进入补货触发</el-button>
      </template>
    </DashboardPageHeader>

    <section class="stats-grid">
      <DashboardStatCard
        title="同步任务数"
        :value="syncState.length"
        hint="当前已纳入同步看板的任务"
      />
      <DashboardStatCard
        title="执行中任务"
        :value="runningTaskCount"
        hint="最近状态仍为执行中的任务"
      />
      <DashboardStatCard
        title="失败任务"
        :value="failedTaskCount"
        :trend="failedTaskCount > 0 ? '需要关注' : '状态正常'"
        :trend-type="failedTaskCount > 0 ? 'negative' : 'positive'"
        hint="最近一次执行失败的同步任务"
      />
      <DashboardStatCard
        title="失败接口调用"
        :value="failedApiCount"
        hint="最近 24 小时累计失败调用"
      />
    </section>

    <section class="chart-grid">
      <DashboardChartCard
        title="同步任务状态分布"
        description="基于最近一次执行状态统计当前同步面板整体健康度。"
        :option="syncStatusChartOption"
        :empty="syncState.length === 0"
        empty-text="暂无同步任务数据"
      />
      <DashboardChartCard
        title="失败接口 Top 8"
        description="按最近 24 小时失败次数排序，帮助快速定位重点异常接口。"
        :option="failedEndpointChartOption"
        :empty="failedEndpointRows.length === 0"
        empty-text="最近 24 小时没有失败接口"
      />
    </section>

    <section class="bottom-grid">
      <DataTableCard title="当前建议摘要" description="当前活动建议单的核心信息。">
        <div v-if="suggestion" class="summary-panel">
          <div class="summary-item">
            <span class="summary-label">建议单编号</span>
            <strong>#{{ suggestion.id }}</strong>
          </div>
          <div class="summary-item">
            <span class="summary-label">状态</span>
            <el-tag :type="suggestionStatus.tagType">{{ suggestionStatus.label }}</el-tag>
          </div>
          <div class="summary-item">
            <span class="summary-label">条目数</span>
            <strong>{{ suggestion.total_items }}</strong>
          </div>
          <div class="summary-item">
            <span class="summary-label">已推送</span>
            <strong>{{ suggestion.pushed_items }}</strong>
          </div>
          <div class="summary-actions">
            <el-button link type="primary" @click="go('/replenishment/current')">查看当前建议</el-button>
            <el-button link @click="go('/replenishment/history')">查看历史记录</el-button>
          </div>
        </div>
        <el-empty v-else description="当前没有可用建议单" :image-size="72" />
      </DataTableCard>

      <DataTableCard title="快捷入口" description="高频入口统一收口在此，便于快速切换。">
        <div class="quick-links">
          <el-button text @click="go('/sync')">查看数据同步</el-button>
          <el-button text @click="go('/troubleshooting/api-monitor')">查看接口监控</el-button>
          <el-button text @click="go('/troubleshooting/performance')">查看性能监控</el-button>
          <el-button text @click="go('/replenishment/current')">查看当前建议</el-button>
          <el-button text @click="go('/replenishment/history')">查看历史记录</el-button>
        </div>
      </DataTableCard>
    </section>
  </div>
</template>

<script setup lang="ts">
import { getApiCallsOverview, type ApiCallsOverview } from '@/api/monitor'
import { getCurrentSuggestion, type SuggestionDetail } from '@/api/suggestion'
import { listSyncState, type SyncStateRow } from '@/api/data'
import DashboardChartCard from '@/components/dashboard/DashboardChartCard.vue'
import DashboardPageHeader from '@/components/dashboard/DashboardPageHeader.vue'
import DashboardStatCard from '@/components/dashboard/DashboardStatCard.vue'
import DataTableCard from '@/components/dashboard/DataTableCard.vue'
import { getSuggestionStatusMeta } from '@/utils/status'
import type { EChartsCoreOption } from 'echarts/core'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const suggestion = ref<SuggestionDetail | null>(null)
const syncState = ref<SyncStateRow[]>([])
const overview = ref<ApiCallsOverview | null>(null)

const suggestionStatus = computed(() =>
  suggestion.value ? getSuggestionStatusMeta(suggestion.value.status) : { label: '暂无', tagType: 'info' as const },
)

const runningTaskCount = computed(() => syncState.value.filter((item) => item.last_status === 'running').length)
const failedTaskCount = computed(() => syncState.value.filter((item) => item.last_status === 'failed').length)
const failedApiCount = computed(() =>
  (overview.value?.endpoints || []).reduce((sum, endpoint) => sum + endpoint.failed_count, 0),
)

const failedEndpointRows = computed(() =>
  [...(overview.value?.endpoints || [])]
    .filter((item) => item.failed_count > 0)
    .sort((a, b) => b.failed_count - a.failed_count)
    .slice(0, 8),
)

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
        avoidLabelOverlap: true,
        label: {
          formatter: '{b}\n{c}',
          color: '#09090b',
          fontSize: 12,
        },
        itemStyle: {
          borderColor: '#ffffff',
          borderWidth: 4,
        },
        data: [
          { name: '成功', value: counts.success || counts.completed || 0, itemStyle: { color: '#16a34a' } },
          { name: '失败', value: counts.failed || 0, itemStyle: { color: '#dc2626' } },
          { name: '执行中', value: counts.running || 0, itemStyle: { color: '#d97706' } },
          { name: '未执行', value: counts.idle || 0, itemStyle: { color: '#a1a1aa' } },
        ].filter((item) => item.value > 0),
      },
    ],
  }
})

const failedEndpointChartOption = computed<EChartsCoreOption>(() => ({
  grid: { left: 24, right: 24, top: 24, bottom: 24, containLabel: true },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: {
    type: 'value',
    axisLabel: { color: '#71717a' },
    splitLine: { lineStyle: { color: '#f4f4f5' } },
  },
  yAxis: {
    type: 'category',
    data: failedEndpointRows.value.map((item) => item.endpoint),
    axisLabel: { color: '#71717a', width: 200, overflow: 'truncate' },
    axisTick: { show: false },
  },
  series: [
    {
      type: 'bar',
      data: failedEndpointRows.value.map((item) => item.failed_count),
      barWidth: 16,
      itemStyle: {
        color: '#18181b',
        borderRadius: [0, 6, 6, 0],
      },
    },
  ],
}))

async function load(): Promise<void> {
  const results = await Promise.allSettled([
    getCurrentSuggestion(),
    listSyncState(),
    getApiCallsOverview(24),
  ])

  const [suggestionResult, syncResult, overviewResult] = results
  suggestion.value = suggestionResult.status === 'fulfilled' ? suggestionResult.value : null

  if (syncResult.status === 'fulfilled') {
    syncState.value = syncResult.value
  }

  if (overviewResult.status === 'fulfilled') {
    overview.value = overviewResult.value
  }
}

function go(path: string): void {
  router.push(path)
}

onMounted(load)
</script>

<style lang="scss" scoped>
.workspace-view {
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

.summary-panel {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.summary-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-4;
}

.summary-label {
  color: $color-text-secondary;
}

.summary-actions {
  display: flex;
  gap: $space-3;
  flex-wrap: wrap;
}

.quick-links {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: $space-2;
}

@media (max-width: 1280px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .stats-grid,
  .chart-grid,
  .bottom-grid {
    grid-template-columns: 1fr;
  }
}
</style>
