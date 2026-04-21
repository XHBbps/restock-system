<template>
  <div class="history-child">
    <el-table v-loading="loading" :data="rows" empty-text="暂无补货建议单">
      <el-table-column label="补货建议单号" min-width="150">
        <template #default="{ row }">
          <span class="order-id">BH-{{ row.id }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.restock_display_status)" size="small">
            {{ row.restock_display_status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最新版本" width="110" align="right">
        <template #default="{ row }">
          <span v-if="row.restock_snapshot_count > 0" class="version-label">
            V{{ row.restock_snapshot_count }}
          </span>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="生成时间" min-width="180">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="230" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" class="history-action" @click="openDetail(row.id)">详情</el-button>
          <el-button
            v-if="row.restock_snapshot_count > 0"
            link
            type="primary"
            class="history-action"
            :loading="downloadingId === row.id"
            @click="downloadLatest(row.id)"
          >
            下载
          </el-button>
          <el-button
            v-if="canVoid(row)"
            link
            type="danger"
            class="history-action history-action--danger"
            :loading="voidingId === row.id"
            @click="voidOne(row)"
          >
            作废
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { downloadSnapshotBlob, listSnapshots } from '@/api/snapshot'
import { listSuggestions, voidSuggestion, type Suggestion } from '@/api/suggestion'
import { getActionErrorMessage } from '@/utils/apiError'
import { triggerBlobDownload } from '@/utils/download'
import { formatDateTime } from '@/utils/format'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const rows = ref<Suggestion[]>([])
const loading = ref(false)
const downloadingId = ref<number | null>(null)
const voidingId = ref<number | null>(null)

function statusTagType(
  status: string,
): 'success' | 'warning' | 'info' | 'danger' {
  if (status === '已导出') return 'success'
  if (status === '未导出') return 'warning'
  if (status === '已作废') return 'danger'
  return 'info'
}

function canVoid(row: Suggestion): boolean {
  return row.status === 'draft'
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const resp = await listSuggestions({
      page: 1,
      page_size: 5000,
      sort_by: 'created_at',
      sort_order: 'desc',
    })
    rows.value = resp.items
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '加载补货历史失败'))
  } finally {
    loading.value = false
  }
}

function openDetail(suggestionId: number): void {
  void router.push(`/restock/suggestions/${suggestionId}/restock`)
}

async function downloadLatest(suggestionId: number): Promise<void> {
  downloadingId.value = suggestionId
  try {
    const snapshots = await listSnapshots(suggestionId, 'restock')
    if (snapshots.length === 0) {
      ElMessage.warning('未找到可下载的快照')
      return
    }
    const latest = snapshots.reduce((max, cur) => (cur.version > max.version ? cur : max))
    const { blob, filename } = await downloadSnapshotBlob(latest.id)
    triggerBlobDownload(blob, filename)
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '下载补货快照失败'))
  } finally {
    downloadingId.value = null
  }
}

async function voidOne(row: Suggestion): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认作废 补货单 #${row.id}？作废后该建议单将归档并无法继续编辑，已导出的快照保留。`,
      '确认作废',
      { type: 'warning', confirmButtonText: '确定作废', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  voidingId.value = row.id
  try {
    await voidSuggestion(row.id)
    ElMessage.success('已作废')
    await load()
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '作废失败'))
  } finally {
    voidingId.value = null
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

.order-id {
  font-family: $font-family-mono;
  color: $color-text-primary;
}

.version-label {
  font-family: $font-family-mono;
  font-weight: $font-weight-medium;
  color: $color-brand-primary;
}

.muted {
  color: $color-text-secondary;
}

.history-action {
  position: relative;
  transition: $transition-fast;

  &:hover:not(:disabled) {
    text-decoration: underline;
    text-underline-offset: 3px;
    background: $color-bg-subtle;
  }
}

.history-action--danger {
  color: $color-danger !important;

  &:hover:not(:disabled) {
    color: #b91c1c !important;
    background: $color-danger-soft !important;
  }
}
</style>
