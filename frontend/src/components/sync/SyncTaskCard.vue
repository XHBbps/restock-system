<template>
  <el-card shadow="never" class="sync-task-card">
    <div class="sync-task-card__top">
      <div>
        <div class="sync-task-card__title">{{ title }}</div>
        <div v-if="description" class="sync-task-card__desc">{{ description }}</div>
      </div>
      <StatusTag :meta="statusMeta" size="small" />
    </div>

    <div class="sync-task-card__meta">
      <div>最近运行：{{ lastRunAt }}</div>
      <div>最近成功：{{ lastSuccessAt }}</div>
      <div v-if="lastError" class="sync-task-card__error">最近错误：{{ lastError }}</div>
      <div v-if="footerHint" class="sync-task-card__hint">{{ footerHint }}</div>
    </div>

    <div class="sync-task-card__actions">
      <slot name="actions">
        <el-button type="primary" :loading="loading" :disabled="disabled" @click="$emit('run')">执行</el-button>
      </slot>
    </div>
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
  footerHint?: string
  loading?: boolean
  disabled?: boolean
}>()

defineEmits<{
  run: []
}>()
</script>

<style lang="scss" scoped>
.sync-task-card {
  height: 100%;
}

.sync-task-card__top {
  display: flex;
  justify-content: space-between;
  gap: $space-3;
}

.sync-task-card__title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}

.sync-task-card__desc,
.sync-task-card__meta {
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.sync-task-card__desc {
  margin-top: $space-2;
}

.sync-task-card__meta {
  display: flex;
  flex-direction: column;
  gap: $space-2;
  margin-top: $space-4;
}

.sync-task-card__error {
  color: $color-danger;
}

.sync-task-card__hint {
  color: $color-text-secondary;
}

.sync-task-card__actions {
  display: flex;
  justify-content: flex-end;
  margin-top: $space-4;
}
</style>
