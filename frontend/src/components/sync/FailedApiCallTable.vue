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
    <el-table-column label="重试状态" width="150" align="center">
      <template #default="{ row }">
        <el-tooltip :disabled="!hasRetryTooltip(row)" placement="top" effect="dark">
          <template #content>
            <div v-if="row.next_retry_at">下次重试：{{ formatDetailTime(row.next_retry_at) }}</div>
            <div v-if="row.last_retry_error">最近错误：{{ row.last_retry_error }}</div>
          </template>
          <span>{{ row.retry_display_text }}</span>
        </el-tooltip>
      </template>
    </el-table-column>
    <el-table-column label="重试次数" width="100" align="right">
      <template #default="{ row }">{{ row.retry_attempt_text }}</template>
    </el-table-column>
    <el-table-column label="操作" width="90" align="center">
      <template #default="{ row }">
        <el-button v-if="row.can_retry && auth.hasPermission('sync:operate')" link type="primary" @click="$emit('retry', row.id)">
          重试
        </el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import dayjs from 'dayjs'
import { formatMonitorEndpoint } from '@/utils/monitoring'
import { formatDetailTime } from '@/utils/format'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

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
    retry_display_status: string
    retry_display_text: string
    retry_attempt_text: string
    auto_retry_attempts: number
    next_retry_at: string | null
    last_retry_error: string | null
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

function hasRetryTooltip(row: { next_retry_at: string | null; last_retry_error: string | null }): boolean {
  return Boolean(row.next_retry_at || row.last_retry_error)
}
</script>
