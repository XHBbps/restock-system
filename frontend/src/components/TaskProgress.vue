<template>
  <el-card v-if="task" class="task-progress" shadow="never">
    <div class="task-header">
      <span class="task-title">{{ task.job_name }}</span>
      <el-tag :type="statusTagType">{{ statusLabel }}</el-tag>
    </div>

    <div v-if="task.current_step" class="task-step">
      {{ task.current_step }}<span v-if="task.step_detail"> - {{ task.step_detail }}</span>
    </div>

    <el-progress
      v-if="!isTerminal"
      :percentage="indeterminatePercent"
      :indeterminate="true"
      :show-text="false"
    />

    <div v-if="task.error_msg" class="task-error">{{ task.error_msg }}</div>
    <div v-if="task.result_summary" class="task-result">{{ task.result_summary }}</div>
  </el-card>
</template>

<script setup lang="ts">
import { useTaskStore } from '@/stores/task'
import { computed, onBeforeUnmount, watch } from 'vue'

const props = defineProps<{ taskId: number | null }>()
const emit = defineEmits<{ terminal: [task: import('@/api/task').TaskRun] }>()

const taskStore = useTaskStore()

const task = computed(() => (props.taskId ? taskStore.tasksById[props.taskId] : null))
const isTerminal = computed(() => (task.value ? taskStore.isTerminal(task.value) : false))

const indeterminatePercent = computed(() => {
  if (!task.value?.total_steps || !task.value.current_step) return 50
  return 50
})

const statusTagType = computed(() => {
  switch (task.value?.status) {
    case 'success':
      return 'success'
    case 'failed':
      return 'danger'
    case 'cancelled':
    case 'skipped':
      return 'info'
    default:
      return 'warning'
  }
})

const statusLabel = computed(() => {
  const s = task.value?.status
  if (!s) return ''
  return (
    {
      pending: '排队中',
      running: '运行中',
      success: '成功',
      failed: '失败',
      skipped: '已跳过',
      cancelled: '已取消',
    } as Record<string, string>
  )[s]
})

watch(
  () => props.taskId,
  (id, oldId) => {
    if (oldId) taskStore.stopPolling(oldId)
    if (id) {
      taskStore.startPolling(id, (t) => emit('terminal', t))
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (props.taskId) taskStore.stopPolling(props.taskId)
})
</script>

<style lang="scss" scoped>
.task-progress {
  margin-top: $space-4;
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: $space-3;
}

.task-title {
  font-weight: $font-weight-medium;
  color: $color-text-primary;
}

.task-step {
  font-size: $font-size-sm;
  color: $color-text-secondary;
  margin-bottom: $space-3;
}

.task-error {
  margin-top: $space-3;
  color: $color-danger;
  font-size: $font-size-sm;
}

.task-result {
  margin-top: $space-3;
  color: $color-success;
  font-size: $font-size-sm;
}
</style>
