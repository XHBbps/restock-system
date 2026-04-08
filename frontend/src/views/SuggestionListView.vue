<template>
  <div class="suggestion-list">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="card-title">当前建议单</span>
          <div class="header-actions">
            <el-input
              v-model="searchSku"
              placeholder="搜索 SKU"
              clearable
              size="default"
              style="width: 200px"
            />
            <el-button type="primary" :loading="pushing" @click="handlePush">
              推送至赛狐 ({{ selected.length }})
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="!suggestion" class="empty">
        <p>暂无活跃建议单。请到"手动同步/计算"页触发计算。</p>
      </div>

      <el-table
        v-else
        :data="filteredItems"
        row-key="id"
        :row-class-name="rowClass"
        @selection-change="handleSelection"
      >
        <el-table-column type="selection" width="48" :selectable="canSelect" />
        <el-table-column label="SKU" min-width="280">
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
        <el-table-column label="总采购量" prop="total_qty" width="120" align="right" />
        <el-table-column label="国家分布" min-width="180">
          <template #default="{ row }">
            <span v-for="(qty, country) in row.country_breakdown" :key="country" class="country-chip">
              {{ country }}: {{ qty }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最早采购" width="140">
          <template #default="{ row }">
            {{ earliestPurchase(row) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.push_status)">{{ statusLabel(row.push_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="goDetail()">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <TaskProgress v-if="pushTaskId" :task-id="pushTaskId" @terminal="onPushDone" />
  </div>
</template>

<script setup lang="ts">
import { getCurrentSuggestion, pushItems, type SuggestionDetail, type SuggestionItem } from '@/api/suggestion'
import SkuCard from '@/components/SkuCard.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const suggestion = ref<SuggestionDetail | null>(null)
const selected = ref<SuggestionItem[]>([])
const searchSku = ref('')
const pushing = ref(false)
const pushTaskId = ref<number | null>(null)

async function loadCurrent(): Promise<void> {
  try {
    suggestion.value = await getCurrentSuggestion()
  } catch (err: unknown) {
    const e = err as { response?: { status?: number } }
    if (e.response?.status === 404) {
      suggestion.value = null
    } else {
      ElMessage.error('加载建议单失败')
    }
  }
}

const filteredItems = computed(() => {
  if (!suggestion.value) return []
  const items = [...suggestion.value.items]
  // 排序：urgent 优先 → 最早 t_purchase → id
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

function earliestPurchase(it: SuggestionItem): string {
  const dates = Object.values(it.t_purchase || {})
  if (!dates.length) return '-'
  return dates.sort()[0]
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

function statusTagType(s: string): string {
  return (
    {
      pushed: 'success',
      push_failed: 'danger',
      blocked: 'info',
      pending: 'warning'
    } as Record<string, string>
  )[s] || 'info'
}

function statusLabel(s: string): string {
  return (
    {
      pending: '待推送',
      pushed: '已推送',
      push_failed: '推送失败',
      blocked: '不可推送'
    } as Record<string, string>
  )[s] || s
}

async function handlePush(): Promise<void> {
  if (!suggestion.value || selected.value.length === 0) {
    ElMessage.warning('请先勾选要推送的条目')
    return
  }
  if (selected.value.length > 50) {
    ElMessage.error('单次最多推送 50 条')
    return
  }
  await ElMessageBox.confirm(
    `确认推送 ${selected.value.length} 条建议至赛狐生成采购单？`,
    '确认推送',
    { type: 'warning' }
  )
  pushing.value = true
  try {
    const resp = await pushItems(
      suggestion.value.id,
      selected.value.map((it) => it.id)
    )
    pushTaskId.value = resp.task_id
  } catch {
    ElMessage.error('推送任务入队失败')
  } finally {
    pushing.value = false
  }
}

async function onPushDone(): Promise<void> {
  ElMessage.success('推送任务完成，刷新数据')
  pushTaskId.value = null
  await loadCurrent()
}

function goDetail(): void {
  if (!suggestion.value) return
  router.push(`/suggestions/${suggestion.value.id}`)
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
  .card-title {
    font-size: $font-size-lg;
    font-weight: $font-weight-semibold;
  }
  .header-actions {
    display: flex;
    gap: $space-3;
  }
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
.empty {
  text-align: center;
  color: $color-text-secondary;
  padding: $space-8;
}

:deep(.row-urgent) {
  background-color: $color-danger-soft !important;
}
</style>
