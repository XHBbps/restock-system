<template>
  <el-card shadow="never" class="dashboard-chart-card">
    <template #header>
      <div class="dashboard-chart-card__header">
        <div>
          <div class="dashboard-chart-card__title">{{ title }}</div>
          <div v-if="description" class="dashboard-chart-card__description">{{ description }}</div>
        </div>
        <div v-if="$slots.actions" class="dashboard-chart-card__actions">
          <slot name="actions" />
        </div>
      </div>
    </template>
    <BaseChart :option="option" :empty="empty" :empty-text="emptyText" />
  </el-card>
</template>

<script setup lang="ts">
import type { EChartsCoreOption } from 'echarts/core'

import BaseChart from '@/components/charts/BaseChart.vue'

defineProps<{
  title: string
  description?: string
  option: EChartsCoreOption
  empty?: boolean
  emptyText?: string
}>()
</script>

<style lang="scss" scoped>
.dashboard-chart-card__header {
  display: flex;
  justify-content: space-between;
  gap: $space-4;
  align-items: center;
}

.dashboard-chart-card__title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}

.dashboard-chart-card__description {
  margin-top: 4px;
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.dashboard-chart-card__actions {
  display: flex;
  gap: $space-3;
  align-items: center;
  flex-wrap: wrap;
}
</style>
