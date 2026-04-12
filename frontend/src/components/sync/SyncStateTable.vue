<template>
  <el-table :data="rows">
    <el-table-column label="任务名称" min-width="180">
      <template #default="{ row }">
        {{ jobLabelMap[row.job_name] || row.job_name }}
      </template>
    </el-table-column>
    <el-table-column label="最近运行" min-width="160">
      <template #default="{ row }">{{ formatTime(row.last_run_at) }}</template>
    </el-table-column>
    <el-table-column label="最近成功" min-width="160">
      <template #default="{ row }">{{ formatTime(row.last_success_at) }}</template>
    </el-table-column>
    <el-table-column label="状态" width="120">
      <template #default="{ row }">
        <StatusTag :meta="getSyncStatusMeta(row.last_status)" size="small" />
      </template>
    </el-table-column>
    <el-table-column label="错误信息" min-width="240">
      <template #default="{ row }">{{ row.last_error || '-' }}</template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import StatusTag from '@/components/StatusTag.vue'
import { getSyncStatusMeta } from '@/utils/status'
import dayjs from 'dayjs'

defineProps<{
  rows: Array<{
    job_name: string
    last_run_at: string | null
    last_success_at: string | null
    last_status: string | null
    last_error: string | null
  }>
  jobLabelMap: Record<string, string>
}>()

function formatTime(value?: string | null): string {
  return value ? dayjs(value).format('MM-DD HH:mm:ss') : '暂无记录'
}
</script>
