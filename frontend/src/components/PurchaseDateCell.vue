<template>
  <div class="purchase-date-cell" :class="levelClass">
    <span>{{ displayDate }}</span>
    <el-tag v-if="badgeText" :type="badgeType" size="small" effect="plain">
      {{ badgeText }}
    </el-tag>
    <span
      v-else-if="note"
      class="purchase-date-cell__note"
      :title="noteTooltip"
    >
      {{ note }}
    </span>
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

// 5 档分级：
// < 0      → 逾期（红色 + 徽章）
// = 0      → 今日到期（橙 + 徽章）
// 1-7      → 临近（橙）
// 8-30     → 正常（深色）
// 31-90    → 宽松（灰色 + "宽松"字样）
// > 90     → 不紧急（灰色 + 徽章）
const badgeText = computed(() => {
  if (diffDays.value === null) return ''
  if (diffDays.value < 0) return `逾期 ${Math.abs(diffDays.value)} 天`
  if (diffDays.value === 0) return '今日到期'
  if (diffDays.value > 90) return '不紧急'
  return ''
})

const badgeType = computed<'danger' | 'warning' | 'info'>(() => {
  if (diffDays.value === null) return 'info'
  if (diffDays.value < 0) return 'danger'
  if (diffDays.value === 0) return 'warning'
  return 'info'    // > 90 天不紧急
})

const note = computed(() => {
  if (diffDays.value === null) return ''
  if (diffDays.value > 30 && diffDays.value <= 90) return '宽松'
  return ''
})

const noteTooltip = computed(() => {
  if (!note.value) return ''
  return '距理论最晚日超过 30 天，采购不紧迫'
})

const levelClass = computed(() => {
  if (diffDays.value === null) return 'is-empty'
  if (diffDays.value < 0) return 'is-overdue'
  if (diffDays.value === 0) return 'is-today'
  if (diffDays.value <= 7) return 'is-warning'
  if (diffDays.value <= 30) return 'is-normal'
  if (diffDays.value <= 90) return 'is-loose'
  return 'is-not-urgent'
})
</script>

<style scoped lang="scss">
.purchase-date-cell {
  display: inline-flex;
  align-items: center;
  gap: $space-2;
  font-weight: $font-weight-medium;
}

.purchase-date-cell__note {
  font-size: $font-size-xs;
  color: $color-text-secondary;
  font-weight: $font-weight-normal;
  cursor: help;
}

.is-empty {
  color: $color-text-secondary;
}

// 紧急 / 正常区间（深色）
.is-normal {
  color: $color-text-primary;
}

// 临近 / 今日（橙色）
.is-warning,
.is-today {
  color: $color-warning;
}

// 逾期（红）
.is-overdue {
  color: $color-danger;
}

// 宽松 / 不紧急（灰）—— 把注意力从这两档移开
.is-loose,
.is-not-urgent {
  color: $color-text-secondary;
  font-weight: $font-weight-normal;
}
</style>
