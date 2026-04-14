<template>
  <el-card shadow="never" class="sync-hero-card">
    <div class="sync-hero-card__content">
      <div class="sync-hero-card__main">
        <div class="sync-hero-card__title">{{ title }}</div>
        <div v-if="description" class="sync-hero-card__desc">{{ description }}</div>
      </div>
      <div class="sync-hero-card__meta">
        <StatusTag :meta="statusMeta" size="small" />
        <span>最近运行：{{ lastRunAt }}</span>
        <span>最近成功：{{ lastSuccessAt }}</span>
      </div>
      <div class="sync-hero-card__actions">
        <el-button type="primary" :loading="loading" :disabled="disabled" @click="$emit('run')">执行全量同步</el-button>
      </div>
    </div>
    <div v-if="lastError" class="sync-hero-card__error">最近错误：{{ lastError }}</div>
  </el-card>
</template>

<script setup lang="ts">
import StatusTag from '@/components/StatusTag.vue'
import type { TagType } from '@/utils/element'

defineProps<{
  title: string
  description?: string
  statusMeta: {
    label: string
    tagType: TagType
  }
  lastRunAt: string
  lastSuccessAt: string
  lastError?: string
  loading?: boolean
  disabled?: boolean
}>()

defineEmits<{
  run: []
}>()
</script>

<style lang="scss" scoped>
.sync-hero-card__content {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr) auto;
  gap: $space-4;
  align-items: center;
}

.sync-hero-card__title {
  font-size: 20px;
  font-weight: $font-weight-semibold;
}

.sync-hero-card__desc,
.sync-hero-card__meta {
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.sync-hero-card__desc {
  margin-top: $space-2;
}

.sync-hero-card__meta {
  display: flex;
  gap: $space-3;
  flex-wrap: wrap;
  align-items: center;
}

.sync-hero-card__actions {
  display: flex;
  justify-content: flex-end;
}

.sync-hero-card__error {
  margin-top: $space-3;
  color: $color-danger;
  font-size: $font-size-sm;
}

@media (max-width: 1100px) {
  .sync-hero-card__content {
    grid-template-columns: 1fr;
  }

  .sync-hero-card__actions {
    justify-content: flex-start;
  }
}
</style>
