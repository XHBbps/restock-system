<template>
  <div class="workspace-view">
    <DashboardPageHeader title="信息总览" />

    <section class="stats-grid">
      <DashboardStatCard
        title="启用 SKU"
        :value="data?.enabled_sku_count ?? 0"
      />
      <DashboardStatCard
        title="当前建议条目"
        :value="data?.suggestion_id != null ? data.suggestion_item_count : '-'"
      />
      <DashboardStatCard
        title="已推送"
        :value="data?.suggestion_id != null ? `${data.pushed_count} / ${data.suggestion_item_count}` : '-'"
      />
      <DashboardStatCard
        title="紧急补货"
        :value="data?.urgent_count ?? 0"
        :trend="(data?.urgent_count ?? 0) > 0 ? `${data!.urgent_count} 个 SKU 需紧急补货` : undefined"
        :trend-type="(data?.urgent_count ?? 0) > 0 ? 'negative' : undefined"
      />
    </section>

    <section class="chart-section">
      <DashboardChartCard
        title="各国库存天数 vs 目标天数"
        :option="stockDaysChartOption"
        :empty="!data || data.country_stock_days.length === 0"
        empty-text="暂无补货计算数据"
      />
    </section>

    <section class="bottom-grid">
      <DataTableCard title="急需补货 SKU">
        <template v-if="data && data.top_urgent_skus.length > 0">
          <div class="urgent-list">
            <div class="urgent-header">
              <span class="urgent-col-product">商品信息</span>
              <span class="urgent-col-countries">需求分布</span>
              <span class="urgent-col-qty">可售天数</span>
            </div>
            <div v-for="item in data.top_urgent_skus" :key="item.commodity_sku" class="urgent-item">
              <div class="urgent-col-product" :title="item.commodity_name || item.commodity_sku">
                <SkuCard :sku="item.commodity_sku" :name="item.commodity_name" :image="item.main_image" />
              </div>
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
        <el-empty v-else description="暂无紧急补货" :image-size="72" />
      </DataTableCard>

      <DataTableCard title="补货概览">
        <div class="right-card-content">
          <div v-if="data?.suggestion_id != null" class="suggestion-progress">
            <div class="suggestion-header">
              <div class="suggestion-meta">
                <strong>#{{ data.suggestion_id }}</strong>
                <el-tag :type="suggestionStatus.tagType" size="small">{{ suggestionStatus.label }}</el-tag>
              </div>
              <el-button link type="primary" @click="go('/restock/current')">查看详情</el-button>
            </div>
            <el-progress
              :percentage="data.suggestion_item_count > 0 ? Math.round(data.pushed_count / data.suggestion_item_count * 100) : 0"
              :stroke-width="10"
            />
            <span class="progress-text">已推送 {{ data.pushed_count }} / 总计 {{ data.suggestion_item_count }}</span>
          </div>

          <template v-if="data && data.top_urgent_skus.length > 0">
            <DashboardChartCard
              title="补货量国家分布"
              :option="countryDistChartOption"
              :empty="false"
              style="box-shadow: none; padding: 0;"
            />
          </template>
          <el-empty v-else-if="!data?.suggestion_id" description="暂无数据" :image-size="72" />
        </div>
      </DataTableCard>
    </section>
  </div>
</template>

<script setup lang="ts">
import { getDashboardOverview, type DashboardOverview } from '@/api/dashboard'
import DashboardChartCard from '@/components/dashboard/DashboardChartCard.vue'
import DashboardPageHeader from '@/components/dashboard/DashboardPageHeader.vue'
import DashboardStatCard from '@/components/dashboard/DashboardStatCard.vue'
import DataTableCard from '@/components/dashboard/DataTableCard.vue'
import SkuCard from '@/components/SkuCard.vue'
import { getSuggestionStatusMeta } from '@/utils/status'
import { getCountryLabel } from '@/utils/countries'
import type { EChartsCoreOption } from 'echarts/core'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const data = ref<DashboardOverview | null>(null)

const suggestionStatus = computed(() =>
  data.value?.suggestion_status
    ? getSuggestionStatusMeta(data.value.suggestion_status)
    : { label: '暂无', tagType: 'info' as const },
)

const stockDaysChartOption = computed<EChartsCoreOption>(() => {
  const items = data.value?.country_stock_days ?? []
  const target = data.value?.target_days ?? 60

  return {
    grid: { left: 24, right: 24, top: 24, bottom: 24, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    xAxis: {
      type: 'category',
      data: items.map((item) => getCountryLabel(item.country)),
      axisLabel: { color: '#71717a' },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: '天数',
      axisLabel: { color: '#71717a' },
      splitLine: { lineStyle: { color: '#f4f4f5' } },
    },
    series: [
      {
        type: 'bar',
        data: items.map((item) => ({
          value: item.avg_sale_days,
          itemStyle: {
            color: item.avg_sale_days >= target ? '#16a34a' : '#ea580c',
            borderRadius: [6, 6, 0, 0],
          },
        })),
        barWidth: 32,
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { type: 'dashed', color: '#dc2626' },
          label: {
            formatter: `目标: ${target}天`,
            position: 'insideEndTop',
            color: '#dc2626',
          },
          data: [{ yAxis: target }],
        },
      },
    ],
  }
})

const countryDistChartOption = computed<EChartsCoreOption>(() => {
  if (!data.value?.top_urgent_skus.length) return {}
  const totals: Record<string, number> = {}
  for (const item of data.value.top_urgent_skus) {
    for (const [country, qty] of Object.entries(item.country_breakdown)) {
      totals[country] = (totals[country] || 0) + qty
    }
  }
  const sorted = Object.entries(totals).sort((a, b) => b[1] - a[1])
  const colors = ['#18181b', '#3b82f6', '#16a34a', '#d97706', '#dc2626', '#8b5cf6', '#06b6d4', '#ec4899']
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, icon: 'circle', textStyle: { color: '#71717a' } },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      itemStyle: { borderColor: '#ffffff', borderWidth: 3 },
      label: { formatter: '{b}\n{d}%', color: '#09090b', fontSize: 11 },
      data: sorted.map(([country, qty], i) => ({
        name: country,
        value: qty,
        itemStyle: { color: colors[i % colors.length] },
      })),
    }],
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
}

.urgent-list {
  display: flex;
  flex-direction: column;
  max-height: 400px;
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

.urgent-item {
  padding-bottom: $space-3;
  border-bottom: 1px solid $color-border-default;

  &:last-child {
    border-bottom: none;
    padding-bottom: 0;
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
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.suggestion-progress {
  display: flex;
  flex-direction: column;
  gap: $space-2;
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
