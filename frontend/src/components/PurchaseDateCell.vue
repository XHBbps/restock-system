<template>
  <div class="purchase-date-cell" :class="levelClass">
    <el-date-picker
      v-if="editable"
      :model-value="date"
      type="date"
      value-format="YYYY-MM-DD"
      size="small"
      class="purchase-date-cell__picker"
      @update:model-value="(value: string | null) => emit('update:date', value)"
    />
    <span v-else class="purchase-date-cell__text">{{ displayDate }}</span>
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
  editable?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:date', value: string | null): void
}>()

const today = dayjs().startOf('day')

const target = computed(() => (props.date ? dayjs(props.date).startOf('day') : null))
const diffDays = computed(() => (target.value ? target.value.diff(today, 'day') : null))

const displayDate = computed(() => (target.value ? target.value.format('YYYY-MM-DD') : '—'))

// 6 档分级（和 editable 无关，始终展示紧急度徽章）：
// < 0      → 逾期（红 + 徽章）
// = 0      → 今日到期（橙 + 徽章）
// 1-7      → 临近（橙）
// 8-30     → 正常（深色）
// 31-90    → 宽松（灰 + note "宽松"）
// > 90     → 不紧急（灰 + 徽章）
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
  return 'info'
})

// "宽松" 仅只读模式显示（编辑时不打扰）
const note = computed(() => {
  if (props.editable) return ''
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

.purchase-date-cell__picker {
  width: 140px;
}

.purchase-date-cell__text {
  white-space: nowrap;
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

.is-normal {
  color: $color-text-primary;
}

.is-warning,
.is-today {
  color: $color-warning;

  // 编辑模式下，给 DatePicker 的 input 染色
  :deep(.el-input__inner) {
    color: $color-warning;
    font-weight: $font-weight-medium;
  }
}

.is-overdue {
  color: $color-danger;

  :deep(.el-input__inner) {
    color: $color-danger;
    font-weight: $font-weight-semibold;
  }
}

.is-loose,
.is-not-urgent {
  color: $color-text-secondary;
  font-weight: $font-weight-normal;

  :deep(.el-input__inner) {
    color: $color-text-secondary;
  }
}
</style>
