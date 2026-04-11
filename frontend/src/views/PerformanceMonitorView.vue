<template>
  <div class="performance-monitor-view">
    <DashboardPageHeader
      eyebrow="Observability"
      title="性能监控"
      description="汇总当前浏览器会话内的页面导航和资源耗时，用 dashboard 方式查看聚合分布与慢资源明细。"
    >
      <template #actions>
        <el-button @click="refresh">刷新</el-button>
        <el-button @click="clearResourceTimings">清理资源缓存</el-button>
        <el-button @click="exportJson">导出 JSON</el-button>
      </template>
    </DashboardPageHeader>

    <section class="stats-grid">
      <DashboardStatCard v-for="metric in navigationMetrics" :key="metric.label" :title="metric.label" :value="metric.value" />
    </section>

    <section class="chart-grid">
      <DashboardChartCard
        title="请求聚合 Top 10"
        description="按平均耗时排序，查看最需要关注的接口/资源。"
        :option="aggregateChartOption"
        :empty="resourceRows.length === 0"
        empty-text="暂无资源聚合数据"
      />
      <DashboardChartCard
        title="资源类型分布"
        description="观察当前会话内资源类型构成。"
        :option="resourceTypeChartOption"
        :empty="resourceTypeRows.length === 0"
        empty-text="暂无资源类型数据"
      />
    </section>

    <section class="table-grid">
      <DataTableCard title="请求聚合" description="按资源名称聚合，适合定位高频慢请求。">
        <el-table :data="pagedResourceRows">
          <el-table-column label="请求名称" min-width="260">
            <template #default="{ row }">{{ row.label }}</template>
          </el-table-column>
          <el-table-column label="请求次数" prop="count" width="100" align="right" />
          <el-table-column label="平均耗时(ms)" prop="avgMs" width="140" align="right" />
          <el-table-column label="P95(ms)" prop="p95Ms" width="120" align="right" />
          <el-table-column label="最大耗时(ms)" prop="maxMs" width="140" align="right" />
        </el-table>
        <template #pagination>
          <TablePaginationBar
            v-model:current-page="resourcePage"
            v-model:page-size="resourcePageSize"
            :total="resourceRows.length"
          />
        </template>
      </DataTableCard>

      <DataTableCard title="最慢资源明细" description="直接查看当前会话耗时最高的资源记录。">
        <el-table :data="pagedSlowResources">
          <el-table-column label="资源名称" min-width="280">
            <template #default="{ row }">{{ row.name }}</template>
          </el-table-column>
          <el-table-column label="类型" prop="initiatorType" width="120" />
          <el-table-column label="耗时(ms)" width="120" align="right">
            <template #default="{ row }">{{ row.duration.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="开始时间(ms)" width="140" align="right">
            <template #default="{ row }">{{ row.startTime.toFixed(2) }}</template>
          </el-table-column>
        </el-table>
        <template #pagination>
          <TablePaginationBar
            v-model:current-page="slowPage"
            v-model:page-size="slowPageSize"
            :total="slowResources.length"
          />
        </template>
      </DataTableCard>
    </section>
  </div>
</template>

<script setup lang="ts">
import DashboardChartCard from '@/components/dashboard/DashboardChartCard.vue'
import DashboardPageHeader from '@/components/dashboard/DashboardPageHeader.vue'
import DashboardStatCard from '@/components/dashboard/DashboardStatCard.vue'
import DataTableCard from '@/components/dashboard/DataTableCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import type { EChartsCoreOption } from 'echarts/core'
import { computed, onMounted, ref } from 'vue'

interface ResourceAggregateRow {
  label: string
  count: number
  avgMs: string
  p95Ms: string
  maxMs: string
}

const navigationEntry = ref<PerformanceNavigationTiming | null>(null)
const resources = ref<PerformanceResourceTiming[]>([])
const resourcePage = ref(1)
const resourcePageSize = ref(10)
const slowPage = ref(1)
const slowPageSize = ref(10)

const navigationMetrics = computed(() => {
  const entry = navigationEntry.value
  if (!entry) {
    return [
      { label: 'TTFB', value: '-' },
      { label: 'DOM Ready', value: '-' },
      { label: '页面完成', value: '-' },
      { label: '资源条数', value: resources.value.length },
    ]
  }
  return [
    { label: 'TTFB', value: `${(entry.responseStart - entry.requestStart).toFixed(2)} ms` },
    { label: 'DOM Ready', value: `${(entry.domContentLoadedEventEnd - entry.startTime).toFixed(2)} ms` },
    { label: '页面完成', value: `${(entry.loadEventEnd - entry.startTime).toFixed(2)} ms` },
    { label: '资源条数', value: resources.value.length },
  ]
})

const resourceRows = computed<ResourceAggregateRow[]>(() => {
  const groups = new Map<string, number[]>()
  for (const item of resources.value) {
    const label = normalizeName(item.name)
    const list = groups.get(label) || []
    list.push(item.duration)
    groups.set(label, list)
  }
  return [...groups.entries()]
    .map(([label, values]) => {
      if (values.length === 0) return null
      const sorted = [...values].sort((a, b) => a - b)
      const total = values.reduce((sum, value) => sum + value, 0)
      const p95Index = Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95))
      return {
        label,
        count: values.length,
        avgMs: (total / values.length).toFixed(2),
        p95Ms: sorted[p95Index].toFixed(2),
        maxMs: sorted[sorted.length - 1].toFixed(2),
      }
    })
    .filter((row): row is ResourceAggregateRow => row !== null)
    .sort((a, b) => Number(b.avgMs) - Number(a.avgMs))
})

const resourceTypeRows = computed(() => {
  const groups = new Map<string, number>()
  for (const item of resources.value) {
    const key = item.initiatorType || 'other'
    groups.set(key, (groups.get(key) || 0) + 1)
  }
  return [...groups.entries()].map(([name, value]) => ({ name, value }))
})

const slowResources = computed(() => [...resources.value].sort((a, b) => b.duration - a.duration))

const pagedResourceRows = computed(() => {
  const start = (resourcePage.value - 1) * resourcePageSize.value
  return resourceRows.value.slice(start, start + resourcePageSize.value)
})

const pagedSlowResources = computed(() => {
  const start = (slowPage.value - 1) * slowPageSize.value
  return slowResources.value.slice(start, start + slowPageSize.value)
})

const aggregateChartOption = computed<EChartsCoreOption>(() => ({
  grid: { left: 24, right: 24, top: 24, bottom: 24, containLabel: true },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: {
    type: 'value',
    axisLabel: { color: '#71717a' },
    splitLine: { lineStyle: { color: '#f4f4f5' } },
  },
  yAxis: {
    type: 'category',
    data: resourceRows.value.slice(0, 10).map((item) => item.label),
    axisLabel: { color: '#71717a', width: 180, overflow: 'truncate' },
    axisTick: { show: false },
  },
  series: [
    {
      type: 'bar',
      data: resourceRows.value.slice(0, 10).map((item) => Number(item.avgMs)),
      barWidth: 16,
      itemStyle: { color: '#18181b', borderRadius: [0, 6, 6, 0] },
    },
  ],
}))

const resourceTypeChartOption = computed<EChartsCoreOption>(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0, icon: 'circle', textStyle: { color: '#71717a' } },
  series: [
    {
      type: 'pie',
      radius: ['48%', '76%'],
      itemStyle: {
        borderColor: '#ffffff',
        borderWidth: 4,
      },
      label: {
        color: '#09090b',
        fontSize: 12,
        formatter: '{b}\n{c}',
      },
      data: resourceTypeRows.value.map((item, index) => ({
        ...item,
        itemStyle: {
          color: ['#18181b', '#3f3f46', '#71717a', '#a1a1aa', '#d4d4d8'][index % 5],
        },
      })),
    },
  ],
}))

function normalizeName(name: string): string {
  try {
    const url = new URL(name)
    return `${url.pathname}${url.search}` || name
  } catch {
    return name
  }
}

function refresh(): void {
  const [entry] = performance.getEntriesByType('navigation') as PerformanceNavigationTiming[]
  navigationEntry.value = entry || null
  resources.value = performance
    .getEntriesByType('resource')
    .filter((entry): entry is PerformanceResourceTiming => entry instanceof PerformanceResourceTiming)
}

function clearResourceTimings(): void {
  performance.clearResourceTimings()
  refresh()
}

function exportJson(): void {
  const payload = {
    navigation: navigationEntry.value,
    resources: resources.value,
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const ts = new Date().toISOString().replace(/[^0-9]/g, '').slice(0, 14)
  link.href = url
  link.download = `restock-performance-${ts}.json`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

onMounted(refresh)
</script>

<style lang="scss" scoped>
.performance-monitor-view {
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
