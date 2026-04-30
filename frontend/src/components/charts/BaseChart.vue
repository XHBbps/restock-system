<template>
  <div class="base-chart">
    <el-empty v-if="empty" :description="emptyText" :image-size="72" />
    <VChart v-else class="base-chart__canvas" :option="option" autoresize />
  </div>
</template>

<script setup lang="ts">
import { use } from 'echarts/core'
import {
  DatasetComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { BarChart, LineChart, PieChart, ScatterChart } from 'echarts/charts'
import type { EChartsCoreOption } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TitleComponent,
  TooltipComponent,
])

defineProps<{
  option: EChartsCoreOption
  empty?: boolean
  emptyText?: string
}>()
</script>

<style lang="scss" scoped>
.base-chart {
  min-height: 280px;
  overflow: hidden;
}

.base-chart__canvas {
  display: block;
  width: 100%;
  min-height: 280px;
  overflow: hidden;
}
</style>
