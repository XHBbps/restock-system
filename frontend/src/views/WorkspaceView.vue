<template>
  <div class="workspace-view">
    <DashboardPageHeader
      title="信息总览"
      description="左侧风险按 SKU+国家 维度展示缓存快照；右侧补货量分布仍基于当前建议补货单。"
    >
      <template #meta>
        <div class="snapshot-meta">
          <el-tag :type="snapshotTagType">{{ snapshotStatusLabel }}</el-tag>
          <span class="snapshot-meta__time">同步时间 {{ snapshotUpdatedText }}</span>
        </div>
      </template>
      <template #actions>
        <el-button :loading="refreshSubmitting" @click="handleRefreshClick">刷新快照</el-button>
      </template>
    </DashboardPageHeader>

    <TaskProgress v-if="currentTaskId" :task-id="currentTaskId" @terminal="onSnapshotTaskDone" />

    <section class="stats-grid">
      <DashboardStatCard
        title="紧急国家商品"
        :value="data?.urgent_count ?? 0"
        :hint="`SKU+国家维度下，可售天数低于提前期 ${leadTimeDays} 天`"
      />
      <DashboardStatCard
        title="临近补货国家商品"
        :value="data?.warning_count ?? 0"
        :hint="`SKU+国家维度下，可售天数介于 ${leadTimeDays} - ${targetDays} 天`"
      />
      <DashboardStatCard
        title="安全国家商品"
        :value="data?.safe_count ?? 0"
        :hint="`SKU+国家维度下，可售天数不少于 ${targetDays} 天`"
      />
      <DashboardStatCard
        title="覆盖国家"
        :value="data?.risk_country_count ?? 0"
        hint="当前快照中可计算风险分层的国家数量"
      />
    </section>

    <section class="chart-section">
      <DashboardChartCard
        title="各国缺货风险分布"
        :option="riskDistributionChartOption"
        :empty="!data || data.country_risk_distribution.length === 0"
        empty-text="暂无补货风险数据"
      />
    </section>

    <section class="bottom-grid">
      <DataTableCard title="急需补货 SKU">
        <div class="urgent-card-content">
          <template v-if="data && data.top_urgent_skus.length > 0">
            <div class="urgent-list">
              <div class="urgent-header">
                <span class="urgent-col-product">商品信息</span>
                <span class="urgent-col-country">国家</span>
                <span class="urgent-col-qty">可售天数</span>
              </div>
              <div
                v-for="item in data.top_urgent_skus"
                :key="`${item.commodity_sku}-${item.country}`"
                class="urgent-item"
              >
                <el-tooltip
                  placement="top-start"
                  :content="item.commodity_name || item.commodity_sku"
                  :show-after="300"
                >
                  <div class="urgent-col-product">
                    <SkuCard
                      :sku="item.commodity_sku"
                      :name="item.commodity_name"
                      :image="item.main_image"
                    />
                  </div>
                </el-tooltip>
                <div class="urgent-col-country">{{ getCountryLabel(item.country) }}</div>
                <div class="urgent-col-qty">{{ formatSaleDays(item.sale_days) }}</div>
              </div>
            </div>
          </template>
          <el-empty v-else description="暂无急需补货项" :image-size="72" />
        </div>
      </DataTableCard>

      <DataTableCard title="补货概览">
        <div class="right-card-content">
          <div
            v-if="data?.suggestion_id != null"
            class="suggestion-progress"
            role="button"
            tabindex="0"
            aria-label="查看当前建议单详情"
            @click="goToCurrentSuggestion"
            @keydown.enter.prevent="goToCurrentSuggestion"
            @keydown.space.prevent="goToCurrentSuggestion"
          >
            <div class="suggestion-header">
              <div class="suggestion-meta-block">
                <strong>#{{ data.suggestion_id }}</strong>
                <el-tag :type="suggestionStatus.tagType" size="small">{{ suggestionStatus.label }}</el-tag>
              </div>
            </div>
            <el-progress
              :percentage="
                data.suggestion_item_count > 0
                  ? Math.round((data.pushed_count / data.suggestion_item_count) * 100)
                  : 0
              "
              :stroke-width="10"
            />
            <span class="progress-text">已推送 {{ data.pushed_count }} / 总计 {{ data.suggestion_item_count }}</span>
          </div>

          <DashboardChartCard
            title="补货量国家分布"
            :option="countryDistChartOption"
            :empty="!data || data.country_restock_distribution.length === 0"
            empty-text="当前没有建议补货单"
            style="box-shadow: none; padding: 0;"
          >
            <template #footer>
              <div class="country-distribution-legend" aria-label="补货量国家分布图例">
                <div
                  v-for="item in countryDistLegendItems"
                  :key="item.country"
                  class="country-distribution-legend__item"
                >
                  <span
                    class="country-distribution-legend__dot"
                    :style="{ backgroundColor: item.color }"
                  />
                  <span class="country-distribution-legend__label">{{ item.label }}</span>
                  <span class="country-distribution-legend__value">{{ item.totalQty }}</span>
                </div>
              </div>
            </template>
          </DashboardChartCard>
        </div>
      </DataTableCard>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { EChartsCoreOption } from 'echarts/core'
import { ElMessage } from 'element-plus'

import {
  getDashboardOverview,
  refreshDashboardSnapshot,
  type DashboardOverview,
} from '@/api/dashboard'
import type { TaskRun } from '@/api/task'
import SkuCard from '@/components/SkuCard.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import DashboardChartCard from '@/components/dashboard/DashboardChartCard.vue'
import DashboardPageHeader from '@/components/dashboard/DashboardPageHeader.vue'
import DashboardStatCard from '@/components/dashboard/DashboardStatCard.vue'
import DataTableCard from '@/components/dashboard/DataTableCard.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { formatUpdateTime } from '@/utils/format'
import { getCountryLabel } from '@/utils/countries'
import { getSuggestionStatusMeta } from '@/utils/status'

const RISK_COLORS = {
  urgent: '#dc2626',
  warning: '#d97706',
  safe: '#16a34a',
}

const PIE_COLORS = ['#18181b', '#3b82f6', '#16a34a', '#d97706', '#dc2626', '#8b5cf6', '#06b6d4', '#ec4899']

const router = useRouter()
const data = ref<DashboardOverview | null>(null)
const loading = ref(false)
const refreshSubmitting = ref(false)
const currentTaskId = ref<number | null>(null)

const leadTimeDays = computed(() => data.value?.lead_time_days ?? 50)
const targetDays = computed(() => data.value?.target_days ?? 60)

const suggestionStatus = computed(() =>
  data.value?.suggestion_status
    ? getSuggestionStatusMeta(data.value.suggestion_status)
    : { label: '暂无', tagType: 'info' as const },
)

const snapshotTagType = computed(() => {
  if (data.value?.snapshot_status === 'refreshing' || currentTaskId.value != null) return 'warning' as const
  if (data.value?.snapshot_updated_at) return 'success' as const
  return 'info' as const
})

const snapshotStatusLabel = computed(() => {
  if (data.value?.snapshot_status === 'refreshing' || currentTaskId.value != null) return '快照刷新中'
  if (data.value?.snapshot_updated_at) return '快照已缓存'
  return '等待生成快照'
})

const snapshotUpdatedText = computed(() => formatUpdateTime(data.value?.snapshot_updated_at))

const countryDistLegendItems = computed(() =>
  (data.value?.country_restock_distribution ?? []).map((item, index) => ({
    country: item.country,
    label: getCountryLabel(item.country),
    totalQty: item.total_qty,
    color: PIE_COLORS[index % PIE_COLORS.length],
  })),
)

const riskDistributionChartOption = computed<EChartsCoreOption>(() => {
  const items = data.value?.country_risk_distribution ?? []

  return {
    grid: { left: 24, right: 24, top: 44, bottom: 24, containLabel: true },
    legend: {
      top: 0,
      icon: 'roundRect',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: '#71717a' },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter(
        params: Array<{
          axisValue: string
          dataIndex?: number
        }>,
      ) {
        const item = items[params[0]?.dataIndex ?? -1]
        if (!item) return ''
        return [
          item.country ? getCountryLabel(item.country) : params[0]?.axisValue ?? '',
          `紧急：${item.urgent_count}`,
          `临近补货：${item.warning_count}`,
          `安全：${item.safe_count}`,
          `总计：${item.total_count}`,
          `提前期阈值：${leadTimeDays.value} 天`,
          `目标库存：${targetDays.value} 天`,
        ].join('<br/>')
      },
    },
    xAxis: {
      type: 'category',
      data: items.map((item) => getCountryLabel(item.country)),
      axisLabel: { color: '#71717a' },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'SKU+国家数',
      axisLabel: { color: '#71717a' },
      splitLine: { lineStyle: { color: '#f4f4f5' } },
    },
    series: [
      {
        name: '紧急',
        type: 'bar',
        barMaxWidth: 18,
        itemStyle: { color: RISK_COLORS.urgent, borderRadius: [6, 6, 0, 0] },
        data: items.map((item) => item.urgent_count),
      },
      {
        name: '临近补货',
        type: 'bar',
        barMaxWidth: 18,
        itemStyle: { color: RISK_COLORS.warning, borderRadius: [6, 6, 0, 0] },
        data: items.map((item) => item.warning_count),
      },
      {
        name: '安全',
        type: 'bar',
        barMaxWidth: 18,
        itemStyle: { color: RISK_COLORS.safe, borderRadius: [6, 6, 0, 0] },
        data: items.map((item) => item.safe_count),
      },
    ],
  }
})

const countryDistChartOption = computed<EChartsCoreOption>(() => {
  const items = data.value?.country_restock_distribution ?? []
  if (!items.length) return {}

  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { show: false },
    series: [
      {
        type: 'pie',
        center: ['50%', '50%'],
        radius: ['46%', '72%'],
        itemStyle: { borderColor: '#ffffff', borderWidth: 3 },
        label: { formatter: '{d}%', color: '#09090b', fontSize: 11 },
        data: items.map((item, index) => ({
          name: getCountryLabel(item.country),
          value: item.total_qty,
          itemStyle: { color: PIE_COLORS[index % PIE_COLORS.length] },
        })),
      },
    ],
  }
})

async function loadDashboard(): Promise<void> {
  loading.value = true
  try {
    const overview = await getDashboardOverview()
    data.value = overview
    currentTaskId.value = overview.snapshot_task_id
  } catch (error) {
    data.value = null
    currentTaskId.value = null
    ElMessage.error(getActionErrorMessage(error, '加载信息总览失败'))
  } finally {
    loading.value = false
  }
}

async function handleRefreshClick(): Promise<void> {
  refreshSubmitting.value = true
  try {
    const result = await refreshDashboardSnapshot()
    currentTaskId.value = result.task_id
    if (result.existing) {
      ElMessage.warning('已有信息总览快照任务在运行，当前复用现有任务进度')
    } else {
      ElMessage.success('信息总览快照刷新任务已入队')
    }
    await loadDashboard()
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '信息总览快照刷新失败'))
  } finally {
    refreshSubmitting.value = false
  }
}

async function onSnapshotTaskDone(task: TaskRun): Promise<void> {
  if (task.status === 'success') {
    ElMessage.success('信息总览快照已刷新')
  } else {
    ElMessage.error(task.error_msg || '信息总览快照刷新失败，请查看任务状态')
  }
  await loadDashboard()
}

function go(path: string): void {
  router.push(path)
}

function goToCurrentSuggestion(): void {
  if (data.value?.suggestion_id == null) return
  go('/restock/current')
}

function formatSaleDays(value: number | null): string {
  if (value == null) return '-'
  if (value < 1) return '<1天'
  return `${value}天`
}

onMounted(loadDashboard)
</script>

<style lang="scss" scoped>
.workspace-view {
  display: flex;
  flex-direction: column;
  gap: $space-6;
}

.snapshot-meta {
  display: flex;
  align-items: center;
  gap: $space-3;
  flex-wrap: wrap;
}

.snapshot-meta__time {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  font-variant-numeric: tabular-nums;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: $space-4;
}

.chart-section {
  display: grid;
  grid-template-columns: 1fr;
  gap: $space-4;
}

.bottom-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: $space-4;

  :deep(.data-table-card) {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  :deep(.data-table-card .el-card__body) {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
}

.urgent-card-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.urgent-list {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
  scrollbar-color: transparent transparent;

  &:hover {
    scrollbar-color: $color-border-default transparent;
  }

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-thumb {
    background: transparent;
    border-radius: 3px;
    transition: background 150ms;
  }

  &:hover::-webkit-scrollbar-thumb {
    background: $color-border-default;
  }
}

.urgent-header {
  display: flex;
  align-items: center;
  padding: 0 0 $space-2;
  border-bottom: 1px solid $color-border-default;
  font-size: $font-size-xs;
  color: $color-text-secondary;
  font-weight: $font-weight-medium;
  position: sticky;
  top: 0;
  background: $color-bg-card;
  z-index: 1;
}

.urgent-item {
  display: flex;
  align-items: center;
  padding: $space-3 0;
  border-bottom: 1px solid $color-border-default;

  &:last-child {
    border-bottom: none;
  }
}

.urgent-col-product {
  flex: 1;
  min-width: 0;
  margin-right: $space-4;

  :deep(.sku-card) {
    min-width: 0;
  }
}

.urgent-col-country {
  width: 140px;
  flex-shrink: 0;
  font-size: $font-size-sm;
  color: $color-text-secondary;
  padding-right: $space-3;
}

.urgent-col-qty {
  width: 88px;
  flex-shrink: 0;
  text-align: right;
  font-size: $font-size-sm;
  font-weight: $font-weight-medium;
  color: $color-text-primary;
  padding-right: $space-3;
}

.right-card-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: $space-4;

  :deep(.dashboard-chart-card) {
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  :deep(.dashboard-chart-card .el-card__body) {
    flex: 1;
    min-height: 0;
  }
}

.country-distribution-legend {
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, max-content));
  justify-content: center;
  align-content: start;
  justify-items: center;
  gap: $space-2 $space-3;
  overflow-y: auto;
  padding-inline: $space-2;
}

.country-distribution-legend__item {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: $space-2;
  padding: 6px 10px;
  border-radius: $radius-pill;
  background: $color-bg-subtle;
}

.country-distribution-legend__dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  flex-shrink: 0;
}

.country-distribution-legend__label {
  min-width: 0;
  font-size: $font-size-xs;
  color: $color-text-primary;
}

.country-distribution-legend__value {
  font-size: $font-size-xs;
  font-weight: $font-weight-medium;
  color: $color-text-secondary;
  font-variant-numeric: tabular-nums;
}

.suggestion-progress {
  display: flex;
  flex-direction: column;
  gap: $space-2;
  padding: $space-4;
  border: 1px solid $color-border-default;
  border-radius: $radius-lg;
  background: $color-bg-subtle;
  cursor: pointer;
  transition:
    border-color 160ms ease,
    box-shadow 160ms ease,
    background-color 160ms ease,
    transform 160ms ease;

  &:hover {
    border-color: $color-border-strong;
    background: $color-bg-subtle-hover;
    box-shadow: $shadow-card-hover;
    transform: translateY(-1px);
  }

  &:focus-visible {
    @include focus-ring;
  }
}

.suggestion-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.suggestion-meta-block {
  display: flex;
  align-items: center;
  gap: $space-2;
}

.progress-text {
  font-size: $font-size-xs;
  color: $color-text-secondary;
  margin-top: $space-1;
}

@media (max-width: 1280px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .country-distribution-legend {
    grid-template-columns: repeat(3, minmax(0, max-content));
  }
}

@media (max-width: 900px) {
  .stats-grid,
  .bottom-grid {
    grid-template-columns: 1fr;
  }

  .country-distribution-legend {
    grid-template-columns: repeat(2, minmax(0, max-content));
  }
}
</style>
