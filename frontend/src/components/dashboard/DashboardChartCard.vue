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
    <div :class="['dashboard-chart-card__content', { 'has-footer': !!$slots.footer }]">
      <div class="dashboard-chart-card__chart">
        <BaseChart :option="option" :empty="empty" :empty-text="emptyText" />
      </div>
      <div v-if="$slots.footer && !empty" class="dashboard-chart-card__footer">
        <slot name="footer" />
      </div>
    </div>
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
.dashboard-chart-card {
  height: 100%;
}

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

.dashboard-chart-card__content {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
}

.dashboard-chart-card__content.has-footer {
  display: grid;
  grid-template-rows: minmax(0, 2fr) minmax(0, 1fr);
  gap: $space-3;
}

.dashboard-chart-card__chart {
  min-height: 0;

  :deep(.base-chart),
  :deep(.base-chart__canvas) {
    height: 100%;
    min-height: 0;
  }
}

.dashboard-chart-card__footer {
  min-height: 0;
  padding-top: $space-2;
  border-top: 1px solid $color-border-default;
}
</style>
