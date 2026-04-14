<template>
  <div class="suggestion-list">
    <PageSectionCard title="补货发起">
      <template #actions>
        <el-tag v-if="suggestion" :type="statusMeta.tagType" size="small">
          {{ statusMeta.label }} · {{ suggestion.total_items }} 条
        </el-tag>
        <el-button @click="loadCurrent">刷新</el-button>
        <el-button v-if="auth.hasPermission('restock:operate')" type="primary" :loading="generating" @click="triggerEngine">生成补货建议</el-button>
      </template>

      <!-- TaskProgress for engine task -->
      <TaskProgress v-if="genTaskId" :task-id="genTaskId" @terminal="onGenDone" />

      <!-- TaskProgress for push task -->
      <TaskProgress v-if="pushTaskId" :task-id="pushTaskId" @terminal="onPushDone" />

      <el-empty
        v-if="!loading && !suggestion"
        description="当前没有活动建议单，点击上方按钮生成补货建议。"
        :image-size="80"
      />

      <template v-else>
        <div class="table-toolbar">
          <div class="toolbar-filters">
            <el-input v-model="searchSku" placeholder="搜索 SKU" clearable style="width: 220px" />
            <el-select v-model="filterPushStatus" placeholder="推送状态" clearable style="width: 140px">
              <el-option label="待推送" value="pending" />
              <el-option label="待处理" value="blocked" />
              <el-option label="已推送" value="pushed" />
              <el-option label="推送失败" value="push_failed" />
            </el-select>
          </div>
          <el-button
            v-if="auth.hasPermission('restock:operate')"
            type="primary"
            :loading="pushing"
            :disabled="selectedIds.length === 0"
            @click="handlePush"
          >
            推送（{{ selectedIds.length }}）
          </el-button>
        </div>
        <el-table
          ref="tableRef"
          v-loading="loading"
          :data="pagedItems"
          row-key="id"
          :row-class-name="rowClass"
          @selection-change="handleSelection"
          @select-all="handleSelectAll"
          @sort-change="handleSortChange"
        >
          <el-table-column type="selection" width="48" :selectable="canSelect" />
          <el-table-column label="商品信息" min-width="320">
            <template #default="{ row }">
              <el-tooltip
                placement="top-start"
                :content="row.commodity_name || row.commodity_sku"
                :show-after="300"
                :hide-after="0"
              >
                <SkuCard
                  :sku="row.commodity_sku"
                  :name="row.commodity_name"
                  :image="row.main_image"
                />
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="总采购量" prop="total_qty" width="120" align="right" sortable="custom" show-overflow-tooltip />
          <el-table-column label="需求分布" min-width="220">
            <template #default="{ row }">
              <el-tooltip
                placement="top"
                :content="Object.entries(row.country_breakdown || {}).map(([c, q]) => `${c}:${q}`).join('  ')"
                :hide-after="0"
              >
                <div class="country-chips">
                  <el-tag v-for="(qty, country) in row.country_breakdown" :key="country" size="small">
                    {{ country }}: {{ qty }}
                  </el-tag>
                </div>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="推送状态" prop="push_status" width="120" sortable="custom">
            <template #default="{ row }">
              <el-tag :type="getSuggestionPushStatusMeta(row.push_status).tagType">
                {{ getSuggestionPushStatusMeta(row.push_status).label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-button link type="primary" @click="goDetail(row.id)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>

        <TablePaginationBar
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="filteredItems.length"
        />
      </template>
    </PageSectionCard>
  </div>
</template>

<script setup lang="ts">
import client from '@/api/client'
import type { TaskRun } from '@/api/task'
import { getCurrentSuggestion, pushItems, type SuggestionDetail, type SuggestionItem } from '@/api/suggestion'
import PageSectionCard from '@/components/PageSectionCard.vue'
import SkuCard from '@/components/SkuCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { getSuggestionPushStatusMeta, getSuggestionStatusMeta } from '@/utils/status'
import {
  applyLocalSort,
  compareNumber,
  normalizeSortOrder,
  type SortChangeEvent,
  type SortState,
} from '@/utils/tableSort'
import { useAuthStore } from '@/stores/auth'
import type { TableInstance } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const auth = useAuthStore()
const tableRef = ref<TableInstance>()
const suggestion = ref<SuggestionDetail | null>(null)
const selectedIds = ref<number[]>([])
const suppressSelectionSync = ref(false)
const searchSku = ref('')
const filterPushStatus = ref('')
const pushing = ref(false)
const generating = ref(false)
const pushTaskId = ref<number | null>(null)
const genTaskId = ref<number | null>(null)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const sortState = ref<SortState>({})

const PUSH_STATUS_SORT_ORDER: Record<SuggestionItem['push_status'], number> = {
  pending: 0,
  blocked: 1,
  push_failed: 2,
  pushed: 3,
}

const statusMeta = computed(() =>
  suggestion.value ? getSuggestionStatusMeta(suggestion.value.status) : { label: '暂无', tagType: 'info' as const },
)

async function loadCurrent(): Promise<void> {
  loading.value = true
  try {
    suggestion.value = await getCurrentSuggestion()
    selectedIds.value = []
  } catch (err: unknown) {
    const e = err as { response?: { status?: number } }
    if (e.response?.status === 404) {
      suggestion.value = null
      selectedIds.value = []
    } else {
      ElMessage.error(getActionErrorMessage(err, '加载当前建议失败'))
    }
  } finally {
    loading.value = false
  }
}

async function triggerEngine(): Promise<void> {
  generating.value = true
  try {
    const { data } = await client.post<{ task_id: number; existing?: boolean }>('/api/engine/run')
    genTaskId.value = data.task_id
    if (data.existing) {
      ElMessage.warning('已有规则引擎任务在运行，当前复用现有任务进度')
    } else {
      ElMessage.success('规则引擎任务已入队')
    }
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '补货任务触发失败'))
  } finally {
    generating.value = false
  }
}

async function onGenDone(task: TaskRun): Promise<void> {
  genTaskId.value = null
  await loadCurrent()
  if (task.status === 'success') {
    ElMessage.success('补货任务已完成，当前建议已刷新')
    return
  }
  ElMessage.error(task.error_msg || '补货任务执行失败，请查看任务详情')
}

const filteredItems = computed(() => {
  if (!suggestion.value) return []
  let items = suggestion.value.items
  if (searchSku.value) {
    const q = searchSku.value.toLowerCase()
    items = items.filter((it) => it.commodity_sku.toLowerCase().includes(q))
  }
  if (filterPushStatus.value) {
    items = items.filter((it) => it.push_status === filterPushStatus.value)
  }
  return items
})

function defaultSuggestionComparator(left: SuggestionItem, right: SuggestionItem): number {
  if (left.urgent !== right.urgent) return left.urgent ? -1 : 1
  return left.id - right.id
}

const sortedItems = computed(() =>
  applyLocalSort(
    filteredItems.value,
    sortState.value,
    {
      total_qty: (left, right) => compareNumber(left.total_qty, right.total_qty),
      push_status: (left, right) =>
        compareNumber(PUSH_STATUS_SORT_ORDER[left.push_status], PUSH_STATUS_SORT_ORDER[right.push_status]),
    },
    defaultSuggestionComparator,
  ),
)

const pagedItems = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return sortedItems.value.slice(start, start + pageSize.value)
})

watch([searchSku, filterPushStatus, pageSize], () => {
  page.value = 1
  selectedIds.value = []
  nextTick(() => tableRef.value?.clearSelection())
})

// Restore checkbox state when changing pages
watch(page, () => {
  nextTick(() => syncTableSelection())
})


function rowClass({ row }: { row: SuggestionItem }): string {
  return row.urgent ? 'row-urgent' : ''
}

function canSelect(row: SuggestionItem): boolean {
  return !row.push_blocker && row.push_status !== 'pushed' && row.push_status !== 'blocked'
}

function handleSelection(rows: SuggestionItem[]): void {
  if (suppressSelectionSync.value) return
  // Sync current page checkbox changes into selectedIds
  const currentPageIdSet = new Set(pagedItems.value.map((r) => r.id))
  const kept = selectedIds.value.filter((id) => !currentPageIdSet.has(id))
  const added = rows.map((r) => r.id)
  selectedIds.value = [...kept, ...added]
}

function handleSelectAll(currentPageSelection: SuggestionItem[]): void {
  // Suppress immediately — selection-change fires synchronously after select-all
  suppressSelectionSync.value = true

  const isSelectingAll = currentPageSelection.length > 0
  if (isSelectingAll) {
    const existing = new Set(selectedIds.value)
    const toAdd = sortedItems.value
      .filter((row) => canSelect(row) && !existing.has(row.id))
      .map((row) => row.id)
    selectedIds.value = [...selectedIds.value, ...toAdd]
  } else {
    selectedIds.value = []
  }

  nextTick(() => {
    syncTableSelection()
  })
}

function syncTableSelection(): void {
  const table = tableRef.value
  if (!table) return
  suppressSelectionSync.value = true
  table.clearSelection()
  const idSet = new Set(selectedIds.value)
  for (const row of pagedItems.value) {
    if (idSet.has(row.id)) {
      table.toggleRowSelection(row, true)
    }
  }
  nextTick(() => { suppressSelectionSync.value = false })
}

function handleSortChange({ prop, order }: SortChangeEvent): void {
  const normalizedOrder = normalizeSortOrder(order)
  sortState.value = normalizedOrder && prop ? { prop, order: normalizedOrder } : {}
  page.value = 1
  selectedIds.value = []
  nextTick(() => tableRef.value?.clearSelection())
}

async function handlePush(): Promise<void> {
  if (!suggestion.value || selectedIds.value.length === 0) {
    ElMessage.warning('请先勾选要推送的条目')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认推送 ${selectedIds.value.length} 条建议生成采购单吗？`,
      '确认推送',
      { type: 'warning' },
    )
  } catch {
    return
  }
  pushing.value = true
  try {
    const resp = await pushItems(
      suggestion.value.id,
      selectedIds.value,
    )
    pushTaskId.value = resp.task_id
    if (resp.existing) {
      ElMessage.warning('已有推送任务在执行，当前复用已有任务进度')
    } else {
      ElMessage.success('推送任务已入队')
    }
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '推送任务入队失败'))
  } finally {
    pushing.value = false
  }
}

async function onPushDone(task: TaskRun): Promise<void> {
  pushTaskId.value = null
  await loadCurrent()
  if (task.status === 'success') {
    ElMessage.success('推送任务已完成，当前建议已刷新')
    return
  }
  ElMessage.error(task.error_msg || '推送任务执行失败，请查看任务详情')
}

function goDetail(id: number): void {
  if (!suggestion.value) return
  router.push(`/restock/suggestions/${suggestion.value.id}?item=${id}`)
}

onMounted(loadCurrent)
</script>

<style lang="scss" scoped>
@use 'sass:color';

.suggestion-list {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-3;
  margin-bottom: $space-4;

  .toolbar-filters {
    display: flex;
    align-items: center;
    gap: $space-3;
  }

  // Unify filter control heights (same as PageSectionCard .section-actions)
  :deep(.el-input),
  :deep(.el-select) {
    --el-component-size: 32px;
  }
}

.country-chips {
  display: flex;
  flex-wrap: nowrap;
  gap: 4px;
  overflow: hidden;
}

:deep(.row-urgent) {
  background-color: $color-danger-soft !important;
}

:deep(.el-table__body tr.row-urgent > td.el-table__cell) {
  background-color: $color-danger-soft !important;
  color: $color-text-primary !important;
}

:deep(.el-table__body tr.row-urgent:hover > td.el-table__cell) {
  background-color: color.mix($color-danger-soft, $color-bg-subtle, $weight: 72%) !important;
  color: $color-text-primary !important;
}

@media (max-width: 900px) {
  .table-toolbar {
    flex-direction: column;
    align-items: flex-start;
  }
}

</style>
