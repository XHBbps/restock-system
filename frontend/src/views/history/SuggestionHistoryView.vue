<template>
  <div class="history-child">
    <SuggestionDetailDialog
      v-model="dialogVisible"
      :suggestion-id="dialogSuggestionId"
      :type="type"
    />
    <el-table v-loading="loading" :data="rows" :empty-text="emptyText" class="history-table">
      <el-table-column :label="idLabel" min-width="150">
        <template #default="{ row }">
          <span class="order-id">{{ idPrefix }}-{{ row.id }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row[displayStatusCodeField])" size="small">
            {{ row[displayStatusField] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最新版本" width="110" align="right">
        <template #default="{ row }">
          <span v-if="row[snapshotCountField] > 0" class="version-label">
            V{{ row[snapshotCountField] }}
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

    <TablePaginationBar
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100, 200]"
      @current-change="load"
      @size-change="onSizeChange"
    />
  </div>
</template>

<script setup lang="ts">
import SuggestionDetailDialog from '@/components/SuggestionDetailDialog.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { deleteSuggestion, listSuggestions, type Suggestion } from '@/api/suggestion'
import { statusTagType } from '@/views/history/displayStatusTag'
import { getActionErrorMessage } from '@/utils/apiError'
import { formatDateTime } from '@/utils/format'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

type HistoryType = 'procurement' | 'restock'

const props = defineProps<{ type: HistoryType }>()

const rows = ref<Suggestion[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const deletingId = ref<number | null>(null)
const dialogVisible = ref(false)
const dialogSuggestionId = ref<number | null>(null)

const idPrefix = computed(() => (props.type === 'procurement' ? 'CG' : 'BH'))
const otherPrefix = computed(() => (props.type === 'procurement' ? 'BH' : 'CG'))
const idLabel = computed(() => (props.type === 'procurement' ? '采购建议单号' : '补货建议单号'))
const emptyText = computed(() =>
  props.type === 'procurement' ? '暂无采购建议单' : '暂无补货建议单',
)
const loadErrorMsg = computed(() =>
  props.type === 'procurement' ? '加载采购历史失败' : '加载补货历史失败',
)
const typeLabel = computed(() => (props.type === 'procurement' ? '采购建议单' : '补货建议单'))
const otherTypeLabel = computed(() =>
  props.type === 'procurement' ? '补货建议单' : '采购建议单',
)

type DisplayStatusField = 'procurement_display_status' | 'restock_display_status'
type DisplayStatusCodeField =
  | 'procurement_display_status_code'
  | 'restock_display_status_code'
type SnapshotCountField = 'procurement_snapshot_count' | 'restock_snapshot_count'

const displayStatusField = computed<DisplayStatusField>(
  () => (props.type === 'procurement' ? 'procurement_display_status' : 'restock_display_status'),
)
const displayStatusCodeField = computed<DisplayStatusCodeField>(
  () =>
    props.type === 'procurement'
      ? 'procurement_display_status_code'
      : 'restock_display_status_code',
)
const snapshotCountField = computed<SnapshotCountField>(
  () => (props.type === 'procurement' ? 'procurement_snapshot_count' : 'restock_snapshot_count'),
)

// 删除条件：整单两种快照都为 0（Q1-c：空归档可删，有快照归档不可删）
function canDelete(row: Suggestion): boolean {
  return (row.procurement_snapshot_count || 0) === 0 && (row.restock_snapshot_count || 0) === 0
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const resp = await listSuggestions({
      page: page.value,
      page_size: pageSize.value,
      sort_by: 'created_at',
      sort_order: 'desc',
    })
    rows.value = resp.items
    total.value = resp.total
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, loadErrorMsg.value))
  } finally {
    loading.value = false
  }
}

function onSizeChange(): void {
  page.value = 1
  void load()
}

function openDetail(suggestionId: number): void {
  dialogSuggestionId.value = suggestionId
  dialogVisible.value = true
}

async function deleteOne(row: Suggestion): Promise<void> {
  if (!canDelete(row)) return
  try {
    await ElMessageBox.confirm(
      `确认删除 ${typeLabel.value} ${idPrefix.value}-${row.id}？删除后对应的${otherTypeLabel.value} ${otherPrefix.value}-${row.id} 也会一并移除（同属一个建议单），操作不可恢复。`,
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
    // 删除后如果当前页空了，自动回退一页
    if (rows.value.length === 1 && page.value > 1) {
      page.value -= 1
    }
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
    color: $color-danger-dark !important;
    background: $color-danger-soft !important;
    box-shadow: 0 1px 2px rgba(220, 38, 38, 0.15);
  }
}
</style>
