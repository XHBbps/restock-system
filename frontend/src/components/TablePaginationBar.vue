<template>
  <el-pagination
    v-model:current-page="currentPage"
    v-model:page-size="pageSize"
    :total="total"
    :page-sizes="pageSizes"
    :layout="paginationLayout"
    :pager-count="isMobile ? 5 : 7"
    :small="isMobile"
    class="table-pagination-bar"
    @current-change="(value) => emit('current-change', value)"
    @size-change="(value) => emit('size-change', value)"
  />
</template>

<script setup lang="ts">
import { useResponsive } from '@/composables/useResponsive'
import { computed } from 'vue'

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

const { isMobile } = useResponsive()
const paginationLayout = computed(() =>
  isMobile.value ? 'prev, pager, next' : 'total, sizes, prev, pager, next',
)
</script>

<style lang="scss" scoped>
.table-pagination-bar {
  margin-top: $space-4;
  justify-content: flex-end;
}

@media (max-width: 767px) {
  .table-pagination-bar {
    justify-content: center;
    overflow-x: auto;
    padding-bottom: 2px;
  }
}
</style>
