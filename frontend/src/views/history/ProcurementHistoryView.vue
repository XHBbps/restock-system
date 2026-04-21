<template>
  <div class="history-child">
    <SuggestionDetailDialog
      v-model="dialogVisible"
      :suggestion-id="dialogSuggestionId"
      type="procurement"
    />
    <el-table v-loading="loading" :data="rows" empty-text="暂无采购建议单">
      <el-table-column label="采购建议单号" min-width="150">
        <template #default="{ row }">
          <span class="order-id">CG-{{ row.id }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.procurement_display_status)" size="small">
            {{ row.procurement_display_status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最新版本" width="110" align="right">
        <template #default="{ row }">
          <span v-if="row.procurement_snapshot_count > 0" class="version-label">
            V{{ row.procurement_snapshot_count }}
          </span>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="生成时间" min-width="180">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" class="history-action" @click="openDetail(row.id)">详情</el-button>
          <el-button
            link
            type="danger"
            class="history-action history-action--danger"
            :disabled="!canDelete(row)"
            :title="canDelete(row) ? '' : '已导出的建议单不可删除'"
            :loading="deletingId === row.id"
            @click="deleteOne(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import SuggestionDetailDialog from '@/components/SuggestionDetailDialog.vue'
import { deleteSuggestion, listSuggestions, type Suggestion } from '@/api/suggestion'
import { getActionErrorMessage } from '@/utils/apiError'
import { formatDateTime } from '@/utils/format'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'

const rows = ref<Suggestion[]>([])
const loading = ref(false)
const deletingId = ref<number | null>(null)
const dialogVisible = ref(false)
const dialogSuggestionId = ref<number | null>(null)

function statusTagType(
  status: string,
): 'success' | 'warning' | 'info' | 'danger' {
  if (status === '已导出') return 'success'
  if (status === '未导出') return 'warning'
  return 'info'  // 已归档
}

// 删除条件：整单两种快照都为 0（Q1-c：空归档可删，有快照归档不可删）
function canDelete(row: Suggestion): boolean {
  return (row.procurement_snapshot_count || 0) === 0 && (row.restock_snapshot_count || 0) === 0
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
    ElMessage.error(getActionErrorMessage(error, '加载采购历史失败'))
  } finally {
    loading.value = false
  }
}

function openDetail(suggestionId: number): void {
  dialogSuggestionId.value = suggestionId
  dialogVisible.value = true
}

async function deleteOne(row: Suggestion): Promise<void> {
  if (!canDelete(row)) return
  try {
    await ElMessageBox.confirm(
      `确认删除 采购建议单 CG-${row.id}？删除后对应的补货建议单 BH-${row.id} 也会一并移除（同属一个建议单），操作不可恢复。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  deletingId.value = row.id
  try {
    await deleteSuggestion(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '删除失败'))
  } finally {
    deletingId.value = null
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

// 操作栏按钮：详情 / 删除 共用
.history-action {
  position: relative;
  padding: 4px 10px;
  border-radius: $radius-md;
  transition: $transition-fast;
  font-weight: $font-weight-medium;

  &:not(.is-disabled):hover {
    background: $color-bg-subtle;
    transform: translateY(-1px);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  }

  &.is-disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
}

.history-action--danger {
  color: $color-danger !important;

  &:not(.is-disabled):hover {
    color: #b91c1c !important;            // red-700
    background: $color-danger-soft !important;
    box-shadow: 0 1px 2px rgba(220, 38, 38, 0.15);
  }
}
</style>
