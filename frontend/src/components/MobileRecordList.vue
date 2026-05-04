<template>
  <div v-loading="loading" class="mobile-record-list">
    <el-empty
      v-if="!loading && items.length === 0"
      :description="emptyText"
      :image-size="72"
    />
    <div v-else class="mobile-record-list__items">
      <article
        v-for="(item, index) in items"
        :key="getKey(item, index)"
        class="mobile-record-card"
      >
        <slot :item="item" :index="index" />
      </article>
    </div>
  </div>
</template>

<script setup lang="ts" generic="T">
const props = withDefaults(
  defineProps<{
    items: T[]
    loading?: boolean
    emptyText?: string
    rowKey?: keyof T | ((item: T, index: number) => string | number)
  }>(),
  {
    loading: false,
    emptyText: '暂无数据',
    rowKey: undefined,
  },
)

function getKey(item: T, index: number): string | number {
  if (typeof props.rowKey === 'function') {
    return props.rowKey(item, index)
  }
  if (props.rowKey) {
    const value = item[props.rowKey]
    if (typeof value === 'string' || typeof value === 'number') {
      return value
    }
  }
  return index
}
</script>

<style scoped lang="scss">
.mobile-record-list {
  min-height: 120px;
}

.mobile-record-list__items {
  display: flex;
  flex-direction: column;
  gap: $space-3;
}

.mobile-record-card {
  padding: $space-4;
  border: 1px solid $color-border-default;
  border-radius: $radius-lg;
  background: $color-bg-card;
  box-shadow: $shadow-sm;
}
</style>
