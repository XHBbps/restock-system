<template>
  <div class="suggestion-list">
    <PageSectionCard title="补货发起">
      <template #actions>
        <el-tag v-if="suggestion" :type="statusMeta.tagType" size="small">
          {{ statusMeta.label }} · {{ suggestion.total_items }} 条
        </el-tag>
        <el-button @click="loadCurrent">刷新</el-button>
        <el-button type="primary" :loading="generating" @click="triggerEngine">生成补货建议</el-button>
      </template>

      <!-- TaskProgress for engine task -->
      <TaskProgress v-if="genTaskId" :task-id="genTaskId" @terminal="onGenDone" />

      <!-- TaskProgress for push task -->
      <TaskProgress v-if="pushTaskId" :task-id="pushTaskId" @terminal="onPushDone" />

      <el-empty
        v-if="!loading && !suggestion"
        description="当前没有活动建议单，点击上方按钮生成补货建议。"
        :image-size="80"
      >
        <el-button type="primary" @click="triggerEngine">生成补货建议</el-button>
      </el-empty>

      <template v-else>
        <div class="table-toolbar">
          <el-input v-model="searchSku" placeholder="搜索 SKU" clearable style="width: 220px" />
          <el-button
            type="primary"
            :loading="pushing"
            :disabled="selected.length === 0 || selected.length > 50"
            @click="handlePush"
          >
            推送（{{ selected.length }}）
          </el-button>
        </div>

        <el-table
          v-loading="loading"
          :data="pagedItems"
          row-key="id"
          :row-class-name="rowClass"
          @selection-change="handleSelection"
        >
          <el-table-column type="selection" width="48" :selectable="canSelect" />
          <el-table-column label="商品信息" min-width="320">
            <template #default="{ row }">
              <el-tooltip
                placement="top-start"
                :content="row.commodity_name || row.commodity_sku"
                :show-after="300"
              >
                <SkuCard
                  :sku="row.commodity_sku"
                  :name="row.commodity_name"
                  :image="row.main_image"
                  :urgent="row.urgent"
                  :blocker="row.push_blocker"
                />
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="总采购量" prop="total_qty" width="120" align="right" sortable show-overflow-tooltip />
          <el-table-column label="需求分布" min-width="220">
            <template #default="{ row }">
              <el-tooltip
                placement="top"
                :content="Object.entries(row.country_breakdown || {}).map(([c, q]) => `${c}:${q}`).join('  ')"
              >
                <div class="country-chips">
                  <el-tag v-for="(qty, country) in row.country_breakdown" :key="country" size="small">
                    {{ country }}: {{ qty }}
                  </el-tag>
                </div>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="最早采购日" width="140" sortable show-overflow-tooltip>
            <template #default="{ row }">
              {{ earliestPurchase(row) }}
            </template>
          </el-table-column>
          <el-table-column label="推送状态" width="120" sortable>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const suggestion = ref<SuggestionDetail | null>(null)
const selected = ref<SuggestionItem[]>([])
const searchSku = ref('')
const pushing = ref(false)
const generating = ref(false)
const pushTaskId = ref<number | null>(null)
const genTaskId = ref<number | null>(null)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

const statusMeta = computed(() =>
  suggestion.value ? getSuggestionStatusMeta(suggestion.value.status) : { label: '暂无', tagType: 'info' as const },
)

async function loadCurrent(): Promise<void> {
  loading.value = true
  try {
    suggestion.value = await getCurrentSuggestion()
    selected.value = []
  } catch (err: unknown) {
    const e = err as { response?: { status?: number } }
    if (e.response?.status === 404) {
      suggestion.value = null
      selected.value = []
    } else {
      ElMessage.error(getActionErrorMessage(err, '加载当前建议失败。'))
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
      ElMessage.warning('已有规则引擎任务在运行，当前复用现有任务进度。')
    } else {
      ElMessage.success('规则引擎任务已入队。')
    }
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '补货任务触发失败。'))
  } finally {
    generating.value = false
  }
}

async function onGenDone(task: TaskRun): Promise<void> {
  genTaskId.value = null
  await loadCurrent()
  if (task.status === 'success') {
    ElMessage.success('补货任务已完成，当前建议已刷新。')
    return
  }
  ElMessage.error(task.error_msg || '补货任务执行失败，请查看任务详情。')
}

const filteredItems = computed(() => {
  if (!suggestion.value) return []
  const items = [...suggestion.value.items]
  items.sort((a, b) => {
    if (a.urgent !== b.urgent) return a.urgent ? -1 : 1
    const ea = earliestPurchase(a)
    const eb = earliestPurchase(b)
    if (ea !== eb) return ea < eb ? -1 : 1
    return a.id - b.id
  })
  if (!searchSku.value) return items
  const q = searchSku.value.toLowerCase()
  return items.filter((it) => it.commodity_sku.toLowerCase().includes(q))
})

const pagedItems = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredItems.value.slice(start, start + pageSize.value)
})

watch([searchSku, pageSize], () => {
  page.value = 1
  selected.value = []
})
watch(page, () => {
  selected.value = []
})

function earliestPurchase(it: SuggestionItem): string {
  const dates = Object.values(it.t_purchase || {})
  if (!dates.length) return '-'
  return [...dates].sort()[0]
}

function rowClass({ row }: { row: SuggestionItem }): string {
  return row.urgent ? 'row-urgent' : ''
}

function canSelect(row: SuggestionItem): boolean {
  return !row.push_blocker && row.push_status !== 'pushed'
}

function handleSelection(rows: SuggestionItem[]): void {
  selected.value = rows
}

async function handlePush(): Promise<void> {
  if (!suggestion.value || selected.value.length === 0) {
    ElMessage.warning('请先勾选要推送的条目。')
    return
  }
  if (selected.value.length > 50) {
    ElMessage.error('单次最多推送 50 条。')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认推送 ${selected.value.length} 条建议生成采购单吗？`,
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
      selected.value.map((it) => it.id),
    )
    pushTaskId.value = resp.task_id
    if (resp.existing) {
      ElMessage.warning('已有推送任务在执行，当前复用已有任务进度。')
    } else {
      ElMessage.success('推送任务已入队。')
    }
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '推送任务入队失败。'))
  } finally {
    pushing.value = false
  }
}

async function onPushDone(task: TaskRun): Promise<void> {
  pushTaskId.value = null
  await loadCurrent()
  if (task.status === 'success') {
    ElMessage.success('推送任务已完成，当前建议已刷新。')
    return
  }
  ElMessage.error(task.error_msg || '推送任务执行失败，请查看任务详情。')
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

:deep(.el-checkbox__inner) {
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
