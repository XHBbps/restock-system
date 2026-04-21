<template>
  <div class="purchase-date-cell" :class="levelClass">
    <span>{{ displayDate }}</span>
    <el-tag v-if="badgeText" :type="badgeType" size="small" effect="plain">
      {{ badgeText }}
    </el-tag>
  </div>
</template>

<script setup lang="ts">
import dayjs from 'dayjs'
import { computed } from 'vue'

const props = defineProps<{
  date: string | null | undefined
}>()

const today = dayjs().startOf('day')

const target = computed(() => (props.date ? dayjs(props.date).startOf('day') : null))
const diffDays = computed(() => (target.value ? target.value.diff(today, 'day') : null))

const displayDate = computed(() => (target.value ? target.value.format('YYYY-MM-DD') : '—'))

const badgeText = computed(() => {
  if (diffDays.value === null) return ''
  if (diffDays.value < 0) return `逾期 ${Math.abs(diffDays.value)} 天`
  if (diffDays.value === 0) return '今日到期'
  return ''
})

const badgeType = computed(() => (diffDays.value !== null && diffDays.value < 0 ? 'danger' : 'warning'))

const levelClass = computed(() => {
  if (diffDays.value === null) return 'is-empty'
  if (diffDays.value < 0) return 'is-overdue'
  if (diffDays.value === 0) return 'is-today'
  if (diffDays.value <= 7) return 'is-warning'
  return 'is-normal'
})
</script>

<style scoped lang="scss">
.purchase-date-cell {
  display: inline-flex;
  align-items: center;
  gap: $space-2;
  font-weight: $font-weight-medium;
}

.is-empty {
  color: $color-text-secondary;
}

.is-normal {
  color: $color-success;
}

.is-warning {
  color: $color-warning;
}

.is-today {
  color: $color-warning;
}

.is-overdue {
  color: $color-danger;
}
</style>
