<template>
  <div class="workspace-view">
    <DashboardPageHeader title="信息总览" />

    <section class="stats-grid">
      <DashboardStatCard
        title="紧急 SKU"
        :value="data?.urgent_count ?? 0"
        :hint="`全部启用 SKU 中低于提前期 ${leadTimeDays} 天`"
      />
      <DashboardStatCard
        title="临近补货"
        :value="data?.warning_count ?? 0"
        hint="全部启用 SKU 中未低于提前期，且低于目标天数"
      />
      <DashboardStatCard
        title="安全 SKU"
        :value="data?.safe_count ?? 0"
        :hint="`全部启用 SKU 中不少于 ${targetDays} 天`"
      />
      <DashboardStatCard
        title="覆盖国家"
        :value="data?.risk_country_count ?? 0"
        hint="基于当前建议单快照"
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
                <span class="urgent-col-countries">需求分布</span>
                <span class="urgent-col-qty">可售天数</span>
              </div>
              <div v-for="item in data.top_urgent_skus" :key="item.commodity_sku" class="urgent-item">
                <el-tooltip
                  placement="top-start"
                  :content="item.commodity_name || item.commodity_sku"
                  :show-after="300"
                >
                  <div class="urgent-col-product">
                    <SkuCard :sku="item.commodity_sku" :name="item.commodity_name" :image="item.main_image" />
                  </div>
                </el-tooltip>
                <el-tooltip
                  placement="top"
                  :content="Object.entries(item.country_breakdown).map(([c, q]) => `${c}:${q}`).join('  ')"
                >
                  <div class="urgent-col-countries">
                    <el-tag v-for="(qty, country) in item.country_breakdown" :key="country" size="small">
                      {{ country }}:{{ qty }}
                    </el-tag>
                  </div>
                </el-tooltip>
                <div class="urgent-col-qty">{{ item.min_sale_days }}天</div>
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
              <div class="suggestion-meta">
                <strong>#{{ data.suggestion_id }}</strong>
                <el-tag :type="suggestionStatus.tagType" size="small">{{ suggestionStatus.label }}</el-tag>
              </div>
            </div>
            <el-progress
              :percentage="data.suggestion_item_count > 0 ? Math.round((data.pushed_count / data.suggestion_item_count) * 100) : 0"
              :stroke-width="10"
            />
            <span class="progress-text">已推送 {{ data.pushed_count }} / 总计 {{ data.suggestion_item_count }}</span>
          </div>

          <DashboardChartCard
            title="补货量国家分布"
            :option="countryDistChartOption"
            :empty="!data || data.country_restock_distribution.length === 0"
            empty-text="暂无补货量数据"
            style="box-shadow: none; padding: 0;"
          />
        </div>
      </DataTableCard>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { EChartsCoreOption } from 'echarts/core'

import { getDashboardOverview, type DashboardOverview } from '@/api/dashboard'
import SkuCard from '@/components/SkuCard.vue'
import DashboardChartCard from '@/components/dashboard/DashboardChartCard.vue'
import DashboardPageHeader from '@/components/dashboard/DashboardPageHeader.vue'
import DashboardStatCard from '@/components/dashboard/DashboardStatCard.vue'
import DataTableCard from '@/components/dashboard/DataTableCard.vue'
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

const leadTimeDays = computed(() => data.value?.lead_time_days ?? 50)
const targetDays = computed(() => data.value?.target_days ?? 60)

const suggestionStatus = computed(() =>
  data.value?.suggestion_status
    ? getSuggestionStatusMeta(data.value.suggestion_status)
    : { label: '暂无', tagType: 'info' as const },
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
          `目标天数：${targetDays.value} 天`,
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
      name: 'SKU 数',
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
    legend: { bottom: 0, icon: 'circle', textStyle: { color: '#71717a' } },
    series: [
      {
        type: 'pie',
        radius: ['45%', '70%'],
        itemStyle: { borderColor: '#ffffff', borderWidth: 3 },
        label: { formatter: '{b}\n{d}%', color: '#09090b', fontSize: 11 },
        data: items.map((item, index) => ({
          name: getCountryLabel(item.country),
          value: item.total_qty,
          itemStyle: { color: PIE_COLORS[index % PIE_COLORS.length] },
        })),
      },
    ],
  }
})

async function load(): Promise<void> {
  try {
    data.value = await getDashboardOverview()
  } catch {
    data.value = null
  }
}

function go(path: string): void {
  router.push(path)
}

function goToCurrentSuggestion(): void {
  if (data.value?.suggestion_id == null) return
  go('/restock/current')
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

.urgent-col-countries {
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-wrap: nowrap;
  gap: 4px;
  overflow: hidden;
}

.urgent-col-qty {
  width: 70px;
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

.suggestion-meta {
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
}

@media (max-width: 900px) {
  .stats-grid,
  .bottom-grid {
    grid-template-columns: 1fr;
  }
}
</style>
