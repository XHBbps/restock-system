<template>
  <div class="suggestion-list">
    <PageSectionCard title="补货发起">
      <template #actions>
        <el-tag v-if="suggestion" :type="statusMeta.tagType" size="small">
          {{ statusMeta.label }} · {{ suggestion.total_items }} 条
        </el-tag>
        <el-tag
          v-if="toggle"
          :type="toggle.enabled ? 'success' : 'info'"
          size="small"
          :title="toggleTitle"
        >
          生成开关：{{ toggle.enabled ? '开启' : '已关闭' }}
        </el-tag>
        <el-button @click="loadCurrent">刷新</el-button>
        <el-button
          v-if="auth.hasPermission('restock:operate')"
          type="primary"
          :loading="generating"
          :disabled="toggle !== null && !toggle.enabled"
          :title="toggle !== null && !toggle.enabled ? '生成开关已关闭，请先在「系统配置」中开启' : ''"
          @click="triggerEngine"
        >生成补货建议</el-button>
      </template>

      <!-- TaskProgress for engine task -->
      <TaskProgress v-if="genTaskId" :task-id="genTaskId" @terminal="onGenDone" />

      <el-empty
        v-if="!loading && !suggestion"
        description="当前没有活动建议单，点击上方按钮生成补货建议。"
        :image-size="80"
      />

      <template v-else>
        <div class="table-toolbar">
          <div class="toolbar-filters">
            <el-input v-model="searchSku" placeholder="搜索 SKU" clearable style="width: 220px" />
          </div>
        </div>
        <el-table
          v-loading="loading"
          :data="pagedItems"
          :row-class-name="rowClass"
          @sort-change="handleSortChange"
        >
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
import { runEngine } from '@/api/engine'
import type { TaskRun } from '@/api/task'
import { getGenerationToggle, type GenerationToggle } from '@/api/config'
import { getCurrentSuggestion, type SuggestionDetail, type SuggestionItem } from '@/api/suggestion'
import PageSectionCard from '@/components/PageSectionCard.vue'
import SkuCard from '@/components/SkuCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { getSuggestionStatusMeta } from '@/utils/status'
import {
  applyLocalSort,
  compareNumber,
  normalizeSortOrder,
  type SortChangeEvent,
  type SortState,
} from '@/utils/tableSort'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const auth = useAuthStore()
const suggestion = ref<SuggestionDetail | null>(null)
const searchSku = ref('')
const generating = ref(false)
const genTaskId = ref<number | null>(null)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const sortState = ref<SortState>({})

const toggle = ref<GenerationToggle | null>(null)

const toggleTitle = computed(() => {
  if (!toggle.value) return ''
  const by = toggle.value.updated_by_name ?? '—'
  const at = toggle.value.updated_at ?? '—'
  return `最近操作：${by} @ ${at}`
})

const statusMeta = computed(() =>
  suggestion.value ? getSuggestionStatusMeta(suggestion.value.status) : { label: '暂无', tagType: 'info' as const },
)

async function loadCurrent(): Promise<void> {
  loading.value = true
  try {
    suggestion.value = await getCurrentSuggestion()
  } catch (err: unknown) {
    const e = err as { response?: { status?: number } }
    if (e.response?.status === 404) {
      suggestion.value = null
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
    const { data } = await runEngine()
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
    },
    defaultSuggestionComparator,
  ),
)

const pagedItems = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return sortedItems.value.slice(start, start + pageSize.value)
})

watch([searchSku, pageSize], () => {
  page.value = 1
})

function rowClass({ row }: { row: SuggestionItem }): string {
  return row.urgent ? 'row-urgent' : ''
}

function handleSortChange({ prop, order }: SortChangeEvent): void {
  const normalizedOrder = normalizeSortOrder(order)
  sortState.value = normalizedOrder && prop ? { prop, order: normalizedOrder } : {}
  page.value = 1
}

function goDetail(id: number): void {
  if (!suggestion.value) return
  router.push(`/restock/suggestions/${suggestion.value.id}?item=${id}`)
}

async function loadToggle(): Promise<void> {
  try {
    toggle.value = await getGenerationToggle()
  } catch {
    // 无权限或后端异常时保持上一次状态，不阻断主流程
  }
}

onMounted(() => {
  void loadCurrent()
  void loadToggle()
})

onActivated(() => {
  void loadToggle()
})
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
