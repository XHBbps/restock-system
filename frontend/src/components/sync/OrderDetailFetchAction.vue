<template>
  <div class="detail-fetch-action">
    <div class="detail-fetch-shell">
      <span class="detail-fetch-label">详情获取</span>
      <el-input-number
        v-model="days"
        :min="1"
        :max="365"
        controls-position="right"
        style="width: 132px"
      />
      <el-button type="primary" :loading="loading" @click="submit">
        确认
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { refetchOrderDetail, type OrderDetailRefetchResult } from '@/api/sync'
import { getActionErrorMessage } from '@/utils/apiError'
import { ElMessage } from 'element-plus'
import { ref } from 'vue'

const emit = defineEmits<{
  started: [taskId: number]
}>()

const days = ref(7)
const loading = ref(false)

function getExistingTaskMessage(result: OrderDetailRefetchResult): string {
  switch (result.active_job_name) {
    case 'refetch_order_detail':
      return '已有详情获取任务在运行，当前复用现有进度'
    case 'sync_order_detail':
      return '订单详情定时同步正在执行，当前复用其进度'
    case 'sync_all':
      return '全量同步正在执行，包含订单详情抓取，当前复用其进度'
    default:
      return '已有相关任务在运行，当前复用现有进度'
  }
}

async function submit(): Promise<void> {
  loading.value = true
  try {
    const result = await refetchOrderDetail({ days: days.value })
    if (!result.task_id) {
      ElMessage.success('当前条件下没有需要获取详情的订单')
      return
    }

    emit('started', result.task_id)
    if (result.existing) {
      ElMessage.warning(getExistingTaskMessage(result))
      return
    }

    const message = result.truncated
      ? `详情获取任务已入队，共 ${result.queued_count} 条，命中数量超过上限，已按上限处理`
      : `详情获取任务已入队，共 ${result.queued_count} 条`
    ElMessage.success(message)
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '详情获取触发失败'))
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.detail-fetch-action {
  display: flex;
  align-items: center;
}

.detail-fetch-shell {
  display: flex;
  align-items: center;
  gap: $space-3;
  padding: $space-2 $space-3;
  border: 1px solid $color-border-default;
  border-radius: $radius-md;
  background: $color-bg-subtle;
}

.detail-fetch-label {
  font-size: $font-size-xs;
  font-weight: $font-weight-semibold;
  color: $color-text-secondary;
  letter-spacing: $tracking-wide;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .detail-fetch-shell {
    width: 100%;
    justify-content: space-between;
    flex-wrap: wrap;
  }
}
</style>
