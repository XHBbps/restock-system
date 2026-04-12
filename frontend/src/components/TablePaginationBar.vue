<template>
  <el-pagination
    v-model:current-page="currentPage"
    v-model:page-size="pageSize"
    :total="total"
    :page-sizes="pageSizes"
    layout="total, sizes, prev, pager, next"
    class="table-pagination-bar"
    @current-change="(value) => emit('current-change', value)"
    @size-change="(value) => emit('size-change', value)"
  />
</template>

<script setup lang="ts">
const emit = defineEmits<{
  'current-change': [value: number]
  'size-change': [value: number]
}>()

withDefaults(
  defineProps<{
    total: number
    pageSizes?: number[]
  }>(),
  {
    pageSizes: () => [10, 20, 50, 100],
  },
)

const currentPage = defineModel<number>('currentPage', { required: true })
const pageSize = defineModel<number>('pageSize', { required: true })
</script>

<style lang="scss" scoped>
.table-pagination-bar {
  margin-top: $space-4;
  justify-content: flex-end;
}
</style>
