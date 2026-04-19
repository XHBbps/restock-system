<template>
  <PageSectionCard title="历史记录">
    <template #actions>
      <el-input
        v-model="sku"
        placeholder="SKU 关键字"
        clearable
        style="width: 200px"
        @clear="() => reload()"
        @keyup.enter="() => reload()"
      />
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        style="width: 280px"
        @change="() => reload()"
      />
      <el-select v-model="displayStatus" placeholder="状态" clearable style="width: 140px" @change="() => reload()">
        <el-option label="未提交" value="pending" />
        <el-option label="已导出" value="exported" />
        <el-option label="已归档" value="archived" />
      </el-select>
    </template>

    <el-table v-loading="loading" :data="rows" @sort-change="handleSortChange">
      <el-table-column label="建议单 ID" prop="id" width="130" sortable="custom" show-overflow-tooltip />
      <el-table-column label="生成时间" prop="created_at" min-width="180" sortable="custom" show-overflow-tooltip>
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="触发方式" prop="triggered_by" width="140" sortable="custom" show-overflow-tooltip>
        <template #default="{ row }">
          {{ triggeredByLabel(row.triggered_by) }}
        </template>
      </el-table-column>
      <el-table-column label="状态" prop="status" width="120" sortable="custom">
        <template #default="{ row }">
          <el-tag :type="getSuggestionDisplayStatusMeta(row.status, row.snapshot_count).tagType">
            {{ getSuggestionDisplayStatusMeta(row.status, row.snapshot_count).label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="条目数" prop="total_items" width="100" align="right" sortable="custom" show-overflow-tooltip />
      <el-table-column label="快照数" prop="snapshot_count" width="100" align="right" sortable="custom" show-overflow-tooltip />
      <el-table-column label="操作" width="160" align="center">
        <template #default="{ row }">
          <div class="row-actions">
            <el-button link type="primary" @click="goDetail(row.id)">详情</el-button>
            <el-button
              v-if="canDelete(row) && auth.hasPermission('history:delete')"
              class="delete-action"
              link
              type="danger"
              @click="remove(row)"
            >
              删除
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <TablePaginationBar
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100]"
      @current-change="handlePageChange"
      @size-change="handlePageSizeChange"
    />
  </PageSectionCard>
</template>

<script setup lang="ts">
import { deleteSuggestion, listSuggestions, type Suggestion } from '@/api/suggestion'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import {
  getSuggestionDisplayStatusMeta,
  type SuggestionDisplayStatus,
} from '@/utils/status'
import { clampPage, formatDateTime } from '@/utils/format'
import { normalizeSortOrder, type SortChangeEvent, type SortState } from '@/utils/tableSort'
import { getActionErrorMessage } from '@/utils/apiError'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const auth = useAuthStore()
const rows = ref<Suggestion[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const sortState = ref<SortState>({ prop: 'created_at', order: 'desc' })

const dateRange = ref<[string, string] | null>(null)
const displayStatus = ref<SuggestionDisplayStatus | undefined>(undefined)
const sku = ref('')

// 派生状态 → 后端 status 参数映射（未提交/已导出都发 draft，再前端二次过滤）
function resolveBackendStatus(
  ds: SuggestionDisplayStatus | undefined,
): string | undefined {
  if (ds === 'pending' || ds === 'exported') return 'draft'
  if (ds === 'archived') return 'archived'
  return undefined
}

async function reload(resetPage = true): Promise<void> {
  if (resetPage) {
    page.value = 1
  }
  loading.value = true
  const requestedPage = page.value
  try {
    const resp = await listSuggestions({
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      status: resolveBackendStatus(displayStatus.value),
      sku: sku.value || undefined,
      page: page.value,
      page_size: pageSize.value,
      sort_by: sortState.value.prop,
      sort_order: sortState.value.order,
    })
    // 未提交/已导出：前端二次按 snapshot_count 过滤当前页
    const ds = displayStatus.value
    const filtered = resp.items.filter((row) => {
      if (ds === 'pending') return row.snapshot_count === 0
      if (ds === 'exported') return row.snapshot_count > 0
      return true
    })
    rows.value = filtered
    total.value = resp.total
    const nextPage = clampPage(page.value, total.value, pageSize.value)
    if (!resetPage && requestedPage !== nextPage) {
      page.value = nextPage
      await reload(false)
    }
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载失败'))
  } finally {
    loading.value = false
  }
}

function triggeredByLabel(triggeredBy: string): string {
  if (triggeredBy === 'manual') return '手动触发'
  if (triggeredBy === 'scheduler') return '自动触发'
  return triggeredBy || '-'
}

function goDetail(id: number): void {
  router.push(`/restock/suggestions/${id}`)
}

function canDelete(row: Suggestion): boolean {
  return row.snapshot_count === 0
}

async function remove(row: Suggestion): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认删除建议单 #${row.id} 吗？删除后不可恢复。`,
      '删除建议单',
      {
        type: 'warning',
        customClass: 'history-delete-confirm',
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
      },
    )
  } catch {
    return
  }

  try {
    await deleteSuggestion(row.id)
    ElMessage.success('已删除')
    await reload(false)
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '删除失败'))
  }
}

function handleSortChange({ prop, order }: SortChangeEvent): void {
  const normalizedOrder = normalizeSortOrder(order)
  sortState.value = normalizedOrder && prop
    ? { prop, order: normalizedOrder }
    : { prop: 'created_at', order: 'desc' }
  void reload(true)
}

onMounted(reload)

function handlePageChange(value: number): void {
  page.value = value
  void reload(false)
}

function handlePageSizeChange(value: number): void {
  pageSize.value = value
  void reload(true)
}
</script>

<style lang="scss" scoped>
.row-actions {
  display: inline-flex;
  align-items: center;
  gap: $space-2;
}

.delete-action {
  color: $color-danger;
}

.delete-action:hover,
.delete-action:focus-visible {
  color: $color-danger;
}
</style>

<style lang="scss">
.history-delete-confirm.el-message-box {
  border: 1px solid $color-border-default;
  border-radius: $radius-xl;
  background: $color-bg-card;
  box-shadow: $shadow-popup;
}

.history-delete-confirm .el-message-box__header {
  padding: $space-5 $space-6 0;
}

.history-delete-confirm .el-message-box__title {
  color: $color-text-primary;
  font-size: $font-size-sm;
  font-weight: $font-weight-semibold;
}

.history-delete-confirm .el-message-box__content {
  padding: $space-3 $space-6 $space-5;
}

.history-delete-confirm .el-message-box__message {
  color: $color-text-secondary;
  font-size: $font-size-sm;
  line-height: 1.6;
}

.history-delete-confirm .el-message-box__btns {
  padding: 0 $space-6 $space-5;
}

.history-delete-confirm .el-message-box__btns .el-button {
  min-width: 88px;
}
</style>
