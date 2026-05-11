<template>
  <div class="scheduler-panel">
    <div class="scheduler-main">
      <div class="scheduler-title">自动同步</div>
      <div class="scheduler-desc">
        调度器统一托管自动同步任务。关闭后将暂停自动同步，手动同步和手动补货计算不受影响。
      </div>
      <div class="scheduler-meta">
        <span>常规同步：每 {{ status?.sync_interval_minutes ?? '-' }} 分钟</span>
        <span>订单处理列表：每 {{ status?.order_sync_interval_minutes ?? '-' }} 分钟</span>
        <span>补货计算：手动生成</span>
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
    order_sync_interval_minutes: number
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
