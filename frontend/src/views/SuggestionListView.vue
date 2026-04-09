<template>
  <div class="suggestion-list">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">当前建议</div>
            <div class="card-meta">当前活动建议单条目列表，支持筛选、分页和批量推送。</div>
          </div>
          <div class="header-actions">
            <el-input v-model="searchSku" placeholder="搜索 SKU" clearable style="width: 220px" />
            <el-button
              type="primary"
              :loading="pushing"
              :disabled="selected.length === 0 || selected.length > 50"
              @click="handlePush"
            >
              推送至赛狐（{{ selected.length }}）
            </el-button>
          </div>
        </div>
      </template>

      <el-empty
        v-if="!suggestion"
        description="当前没有活动建议单，请先在补货触发页执行规则引擎。"
        :image-size="80"
      >
        <el-button type="primary" @click="goRun">前往补货触发</el-button>
      </el-empty>

      <template v-else>
        <el-table
          :data="pagedItems"
          row-key="id"
          :row-class-name="rowClass"
          @selection-change="handleSelection"
        >
          <el-table-column type="selection" width="48" :selectable="canSelect" />
          <el-table-column label="商品信息" min-width="320" show-overflow-tooltip>
            <template #default="{ row }">
              <SkuCard
                :sku="row.commodity_sku"
                :name="row.commodity_name"
                :image="row.main_image"
                :urgent="row.urgent"
                :blocker="row.push_blocker"
              />
            </template>
          </el-table-column>
          <el-table-column label="总采购量" prop="total_qty" width="120" align="right" show-overflow-tooltip />
          <el-table-column label="国家分布" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-for="(qty, country) in row.country_breakdown" :key="country" class="country-chip">
                {{ country }}: {{ qty }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="最早采购日" width="140" show-overflow-tooltip>
            <template #default="{ row }">
              {{ earliestPurchase(row) }}
            </template>
          </el-table-column>
          <el-table-column label="推送状态" width="120" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag :type="getSuggestionPushStatusMeta(row.push_status).tagType">
                {{ getSuggestionPushStatusMeta(row.push_status).label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" align="center" show-overflow-tooltip>
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
    </el-card>

    <TaskProgress v-if="pushTaskId" :task-id="pushTaskId" @terminal="onPushDone" />
  </div>
</template>

<script setup lang="ts">
import { getCurrentSuggestion, pushItems, type SuggestionDetail, type SuggestionItem } from '@/api/suggestion'
import SkuCard from '@/components/SkuCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import { getSuggestionPushStatusMeta } from '@/utils/status'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const suggestion = ref<SuggestionDetail | null>(null)
const selected = ref<SuggestionItem[]>([])
const searchSku = ref('')
const pushing = ref(false)
const pushTaskId = ref<number | null>(null)
const page = ref(1)
const pageSize = ref(20)

async function loadCurrent(): Promise<void> {
  try {
    suggestion.value = await getCurrentSuggestion()
  } catch (err: unknown) {
    const e = err as { response?: { status?: number } }
    if (e.response?.status === 404) {
      suggestion.value = null
    } else {
      ElMessage.error('加载当前建议失败。')
    }
  }
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
  await ElMessageBox.confirm(
    `确认推送 ${selected.value.length} 条建议至赛狐生成采购单吗？`,
    '确认推送',
    { type: 'warning' },
  )
  pushing.value = true
  try {
    const resp = await pushItems(
      suggestion.value.id,
      selected.value.map((it) => it.id),
    )
    pushTaskId.value = resp.task_id
  } catch {
    ElMessage.error('推送任务入队失败。')
  } finally {
    pushing.value = false
  }
}

async function onPushDone(): Promise<void> {
  ElMessage.success('推送任务已结束，正在刷新当前建议。')
  pushTaskId.value = null
  await loadCurrent()
}

function goDetail(id: number): void {
  router.push(`/replenishment/suggestions/${id}`)
}

function goRun(): void {
  router.push('/replenishment/run')
}

onMounted(loadCurrent)
</script>

<style lang="scss" scoped>
.suggestion-list {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-4;
}

.card-title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}

.card-meta {
  margin-top: 4px;
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.header-actions {
  display: flex;
  gap: $space-3;
  flex-wrap: wrap;
}

.country-chip {
  display: inline-block;
  padding: 2px 8px;
  margin-right: $space-2;
  background: $color-brand-primary-soft;
  color: $color-brand-primary;
  border-radius: $radius-pill;
  font-size: $font-size-xs;
}

:deep(.row-urgent) {
  background-color: $color-danger-soft !important;
}

@media (max-width: 900px) {
  .card-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
