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
          <el-table :data="data.top_urgent_skus" stripe>
            <el-table-column prop="commodity_sku" label="SKU" min-width="180" />
            <el-table-column prop="total_qty" label="建议补货量" width="120" align="right" />
            <el-table-column label="国家分布" min-width="200">
              <template #default="{ row }">
                <el-tag
                  v-for="(qty, country) in row.country_breakdown"
                  :key="country"
                  size="small"
                  class="country-tag"
                >
                  {{ country }}:{{ qty }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </template>
        <el-empty v-else description="暂无紧急补货" :image-size="72" />
      </DataTableCard>

      <DataTableCard title="当前建议">
        <div v-if="data?.suggestion_id != null" class="summary-panel">
          <div class="summary-item">
            <span class="summary-label">建议单编号</span>
            <strong>#{{ data.suggestion_id }}</strong>
          </div>
          <div class="summary-item">
            <span class="summary-label">状态</span>
            <el-tag :type="suggestionStatus.tagType">{{ suggestionStatus.label }}</el-tag>
          </div>
          <div class="summary-item">
            <span class="summary-label">条目数</span>
            <strong>{{ data.suggestion_item_count }}</strong>
          </div>
          <div class="summary-item">
            <span class="summary-label">已推送</span>
            <strong>{{ data.pushed_count }}</strong>
          </div>
          <div class="summary-actions">
            <el-button link type="primary" @click="go('/restock/current')">查看详情</el-button>
          </div>
        </div>
        <el-empty v-else description="当前没有活跃建议单" :image-size="72" />
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

.country-tag {
  margin-right: 4px;
  margin-bottom: 2px;
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
