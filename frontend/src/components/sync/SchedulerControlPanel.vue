<template>
  <div class="scheduler-panel">
    <div class="scheduler-main">
      <div class="scheduler-title">自动同步</div>
      <div class="scheduler-desc">
        调度器统一托管自动同步任务。关闭后将暂停自动同步和定时补货计算，手动同步不受影响。
      </div>
      <div class="scheduler-meta">
        <span>同步间隔：每 {{ status?.sync_interval_minutes ?? '-' }} 分钟</span>
        <span>自动计算：{{ formatCron(status?.calc_cron) }}</span>
      </div>
    </div>
    <div class="scheduler-actions">
      <StatusTag :meta="statusMeta" />
      <el-switch
        :model-value="Boolean(status?.enabled)"
        :loading="toggleLoading"
        @change="onToggle"
      />
      <el-button :loading="refreshing" @click="$emit('refresh')">刷新状态</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import StatusTag from '@/components/StatusTag.vue'
import { computed } from 'vue'

const props = defineProps<{
  status: {
    enabled: boolean
    running: boolean
    timezone: string
    sync_interval_minutes: number
    calc_cron: string
  } | null
  refreshing: boolean
  toggleLoading: boolean
}>()

const emit = defineEmits<{
  refresh: []
  toggle: [enabled: boolean]
}>()

const statusMeta = computed(() => {
  if (!props.status) {
    return { label: '未加载', tagType: 'info' as const }
  }
  return props.status.enabled
    ? { label: '调度器已开启', tagType: 'success' as const }
    : { label: '调度器已关闭', tagType: 'warning' as const }
})

const CRON_LABELS: Record<string, string> = {
  '0 6 * * *': '每天 06:00',
  '0 8 * * *': '每天 08:00',
  '0 12 * * *': '每天 12:00',
  '0 20 * * *': '每天 20:00',
  '0 */12 * * *': '每 12 小时',
  '0 */6 * * *': '每 6 小时',
}

function formatCron(cron?: string): string {
  if (!cron) return '-'
  return CRON_LABELS[cron] || cron
}

function onToggle(value: string | number | boolean): void {
  emit('toggle', Boolean(value))
}
</script>

<style lang="scss" scoped>
.scheduler-panel {
  display: flex;
  justify-content: space-between;
  gap: $space-4;
  align-items: center;
}

.scheduler-title {
  font-size: 20px;
  font-weight: $font-weight-semibold;
}

.scheduler-desc {
  margin-top: $space-2;
  color: $color-text-secondary;
}

.scheduler-meta {
  display: flex;
  gap: $space-4;
  flex-wrap: wrap;
  margin-top: $space-3;
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.scheduler-actions {
  display: flex;
  align-items: center;
  gap: $space-3;
  flex-wrap: wrap;
  justify-content: flex-end;
}

@media (max-width: 900px) {
  .scheduler-panel {
    flex-direction: column;
    align-items: flex-start;
  }

  .scheduler-actions {
    justify-content: flex-start;
  }
}
</style>
