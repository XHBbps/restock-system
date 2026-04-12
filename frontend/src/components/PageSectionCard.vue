<template>
  <el-card shadow="never">
    <template #header>
      <div class="section-header">
        <div>
          <div class="section-title">{{ title }}</div>
          <div v-if="description" class="section-description">{{ description }}</div>
        </div>
        <div v-if="$slots.actions" class="section-actions">
          <slot name="actions" />
        </div>
      </div>
    </template>
    <slot />
  </el-card>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<style lang="scss" scoped>
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-4;
}

.section-title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}

.section-description {
  margin-top: 4px;
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.section-actions {
  display: flex;
  gap: $space-3;
  align-items: center;
  flex-wrap: wrap;

  // Unify filter control heights across all pages
  :deep(.el-input),
  :deep(.el-select),
  :deep(.el-date-editor) {
    --el-component-size: 32px;
  }
}

@media (max-width: 900px) {
  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
