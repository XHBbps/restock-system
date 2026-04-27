<template>
  <el-table :data="rows">
    <el-table-column label="调用时间" min-width="160">
      <template #default="{ row }">{{ formatTime(row.called_at) }}</template>
    </el-table-column>
    <el-table-column label="接口名称" min-width="220">
      <template #default="{ row }">
        <span :title="getEndpointDisplay(row.endpoint).raw">
          {{ getEndpointDisplay(row.endpoint).label }}
        </span>
      </template>
    </el-table-column>
    <el-table-column label="耗时(ms)" prop="duration_ms" width="100" align="right" />
    <el-table-column label="HTTP 状态" prop="http_status" width="100" align="center" />
    <el-table-column label="外部返回码" prop="saihu_code" width="120" align="center" />
    <el-table-column label="错误信息" min-width="260">
      <template #default="{ row }">{{ row.saihu_msg || row.error_type || '-' }}</template>
    </el-table-column>
    <el-table-column label="重试状态" width="130" align="center">
      <template #default="{ row }">{{ retryStatusLabel(row.retry_status) }}</template>
    </el-table-column>
    <el-table-column label="重试次数" width="100" align="right">
      <template #default="{ row }">{{ row.auto_retry_attempts ?? 0 }}/5</template>
    </el-table-column>
    <el-table-column label="操作" width="90" align="center">
      <template #default="{ row }">
        <el-button v-if="row.can_retry" link type="primary" @click="$emit('retry', row.id)">
          重试
        </el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import dayjs from 'dayjs'
import { formatMonitorEndpoint } from '@/utils/monitoring'

defineProps<{
  rows: Array<{
    id: number
    endpoint: string
    called_at: string
    duration_ms: number | null
    http_status: number | null
    saihu_code: number | null
    saihu_msg: string | null
    error_type: string | null
    retry_status: string | null
    auto_retry_attempts: number
    can_retry: boolean
  }>
}>()

defineEmits<{
  retry: [id: number]
}>()

function formatTime(value: string): string {
  return dayjs(value).format('MM-DD HH:mm:ss')
}

function getEndpointDisplay(endpoint: string) {
  return formatMonitorEndpoint(endpoint)
}

function retryStatusLabel(status: string | null): string {
  switch (status) {
    case 'queued':
      return '待重试'
    case 'resolved':
      return '已解决'
    case 'permanent':
      return '永久失败'
    case 'unsupported':
      return '不支持'
    default:
      return '-'
  }
}
</script>
