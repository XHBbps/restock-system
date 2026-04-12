<template>
  <el-card shadow="never" class="dashboard-stat-card">
    <div class="dashboard-stat-card__header">
      <div class="dashboard-stat-card__title">{{ title }}</div>
      <slot name="icon" />
    </div>
    <div class="dashboard-stat-card__value">{{ value }}</div>
    <div class="dashboard-stat-card__footer">
      <span v-if="trend" :class="['dashboard-stat-card__trend', `is-${trendType || 'neutral'}`]">
        {{ trend }}
      </span>
      <span v-if="hint" class="dashboard-stat-card__hint">{{ hint }}</span>
    </div>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  value: string | number
  hint?: string
  trend?: string
  trendType?: 'positive' | 'negative' | 'neutral'
}>()
</script>

<style lang="scss" scoped>
.dashboard-stat-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-3;
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.dashboard-stat-card__value {
  margin-top: $space-3;
  font-size: 32px;
  line-height: 1;
  font-weight: $font-weight-semibold;
  letter-spacing: $tracking-tight;
}

.dashboard-stat-card__footer {
  display: flex;
  gap: $space-3;
  align-items: center;
  flex-wrap: wrap;
  margin-top: $space-3;
}

.dashboard-stat-card__trend,
.dashboard-stat-card__hint {
  font-size: $font-size-xs;
}

.dashboard-stat-card__hint {
  color: $color-text-secondary;
}

.dashboard-stat-card__trend.is-positive {
  color: $color-success;
}

.dashboard-stat-card__trend.is-negative {
  color: $color-danger;
}

.dashboard-stat-card__trend.is-neutral {
  color: $color-text-secondary;
}
</style>
