<template>
  <div class="history-child">
    <el-table v-loading="loading" :data="rows" empty-text="暂无补货快照记录">
      <el-table-column label="版本" width="120">
        <template #default="{ row }">v{{ row.version }}</template>
      </el-table-column>
      <el-table-column label="时间" min-width="180">
        <template #default="{ row }">{{ formatDateTime(row.exported_at) }}</template>
      </el-table-column>
      <el-table-column label="导出人" min-width="140">
        <template #default="{ row }">{{ row.exported_by_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="item 数" prop="item_count" width="120" align="right" />
      <el-table-column label="文件大小" width="140" align="right">
        <template #default="{ row }">{{ formatBytes(row.file_size_bytes) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" align="center">
        <template #default="{ row }">
          <el-button link type="primary" :loading="downloadingId === row.id" @click="download(row.id)">
            下载
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { downloadSnapshotBlob, listSnapshots, type SnapshotOut } from '@/api/snapshot'
import { listSuggestions } from '@/api/suggestion'
import { getActionErrorMessage } from '@/utils/apiError'
import { triggerBlobDownload } from '@/utils/download'
import { formatDateTime } from '@/utils/format'
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

const rows = ref<SnapshotOut[]>([])
const loading = ref(false)
const downloadingId = ref<number | null>(null)

function formatBytes(value: number | null): string {
  if (!value || value <= 0) return '-'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const resp = await listSuggestions({ page: 1, page_size: 5000, sort_by: 'created_at', sort_order: 'desc' })
    const suggestions = resp.items.filter((row) => row.restock_snapshot_count > 0)
    const snapshots = await Promise.all(suggestions.map((row) => listSnapshots(row.id, 'restock')))
    rows.value = snapshots
      .flat()
      .sort((left, right) => right.exported_at.localeCompare(left.exported_at))
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '加载补货历史失败'))
  } finally {
    loading.value = false
  }
}

async function download(snapshotId: number): Promise<void> {
  downloadingId.value = snapshotId
  try {
    const { blob, filename } = await downloadSnapshotBlob(snapshotId)
    triggerBlobDownload(blob, filename)
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '下载补货快照失败'))
  } finally {
    downloadingId.value = null
  }
}

onMounted(() => {
  void load()
})
</script>

<style scoped lang="scss">
.history-child {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}
</style>
