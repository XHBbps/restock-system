<template>
  <el-card shadow="never" class="data-table-card">
    <template #header>
      <div class="data-table-card__header">
        <div>
          <div class="data-table-card__title">{{ title }}</div>
          <div v-if="description" class="data-table-card__description">{{ description }}</div>
        </div>
        <div v-if="$slots.toolbar" class="data-table-card__toolbar">
          <slot name="toolbar" />
        </div>
      </div>
    </template>
    <slot />
    <div v-if="$slots.pagination" class="data-table-card__pagination">
      <slot name="pagination" />
    </div>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<style lang="scss" scoped>
.data-table-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-4;
}

.data-table-card__title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}

.data-table-card__description {
  margin-top: 4px;
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.data-table-card__toolbar {
  display: flex;
  gap: $space-3;
  align-items: center;
  flex-wrap: wrap;
}

.data-table-card__pagination {
  margin-top: $space-4;
}

@media (max-width: 900px) {
  .data-table-card__header {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 767px) {
  .data-table-card__header {
    gap: $space-3;
  }

  .data-table-card__title {
    font-size: $font-size-base;
  }

  .data-table-card__toolbar {
    width: 100%;
    align-items: stretch;
  }

  .data-table-card__toolbar :deep(.el-button),
  .data-table-card__toolbar :deep(.el-input),
  .data-table-card__toolbar :deep(.el-select),
  .data-table-card__toolbar :deep(.el-switch) {
    width: 100% !important;
  }
}
</style>
