<template>
  <div class="detail-view">
    <el-card v-loading="loading" v-if="suggestion" shadow="never">
      <template #header>
        <div class="header-row">
          <div class="header-main">
            <div>
              <span class="title">建议单 #{{ suggestion.id }}</span>
              <el-tag style="margin-left: 12px" :type="suggestionStatusMeta.tagType">
                {{ suggestionStatusMeta.label }}
              </el-tag>
            </div>
            <div class="summary-meta">
              <span class="summary-chip">条目数：{{ suggestion.total_items }}</span>
              <span class="summary-chip">触发方式：{{ triggeredByLabel }}</span>
              <span class="summary-chip">创建时间：{{ formatDateTime(suggestion.created_at) }}</span>
            </div>
          </div>
          <div class="actions">
            <el-button @click="goBack">返回</el-button>
          </div>
        </div>
      </template>

      <el-alert
        type="info"
        :closable="false"
        title="当前仅支持修改总采购量；国家分量、仓库分量、采购时间和发货时间为只读，保存后将按服务端最新结果刷新。"
      />

      <el-collapse v-model="expanded">
        <el-collapse-item v-for="item in suggestion.items" :key="item.id" :name="item.id">
          <template #title>
            <div :id="`suggestion-item-${item.id}`" class="item-header">
              <SkuCard
                :sku="item.commodity_sku"
                :name="item.commodity_name"
                :image="item.main_image"
                :urgent="item.urgent"
                :blocker="item.push_blocker"
              />
              <div class="item-stats">
                <span class="stat-label">总采购量</span>
                <strong>{{ item.total_qty }}</strong>
              </div>
            </div>
          </template>

          <div class="item-body">
            <div class="section">
              <div class="section-title">总采购量</div>
              <el-input-number v-model="editing[item.id].total_qty" :min="0" size="small" />
            </div>

            <div class="section">
              <div class="section-title">各国分量 / 各仓分量</div>
              <el-table :data="countryRows(item)" size="small">
                <el-table-column prop="country" label="国家" width="80" sortable show-overflow-tooltip />
                <el-table-column prop="qty" label="国家总量" width="100" sortable show-overflow-tooltip />
                <el-table-column label="各仓明细" show-overflow-tooltip>
                  <template #default="{ row }">
                    <template v-if="Object.keys(row.warehouses).length">
                      <span v-for="(wq, w) in row.warehouses" :key="w" class="warehouse-chip">
                        {{ w }}: {{ wq }}
                      </span>
                    </template>
                    <span v-else class="allocation-text">未拆分</span>
                  </template>
                </el-table-column>
                <el-table-column label="拆分依据" min-width="220" show-overflow-tooltip>
                  <template #default="{ row }">
                    <div v-if="row.allocation" class="allocation-meta">
                      <el-tag
                        :type="allocationModeTagType(row.allocation.allocation_mode)"
                        size="small"
                      >
                        {{ allocationModeLabel(row.allocation.allocation_mode) }}
                      </el-tag>
                      <span class="allocation-text">{{ allocationSummary(row.allocation) }}</span>
                      <span class="allocation-text">
                        可用仓：{{ row.allocation.eligible_warehouses.join(', ') || '-' }}
                      </span>
                    </div>
                    <span v-else class="allocation-text">-</span>
                  </template>
                </el-table-column>
                <el-table-column prop="t_purchase" label="采购时间" width="120" sortable show-overflow-tooltip />
                <el-table-column prop="t_ship" label="发货时间" width="120" sortable show-overflow-tooltip />
              </el-table>
            </div>

            <div v-if="item.overstock_countries?.length" class="section">
              <div class="section-title">积压国家（只读）</div>
              <el-tag
                v-for="country in item.overstock_countries"
                :key="country"
                type="warning"
                size="small"
                style="margin-right: 8px"
              >
                {{ country }}
              </el-tag>
            </div>

            <div class="section">
              <div class="section-title">状态信息</div>
              <div class="status-grid">
                <div class="status-row">
                  <span class="status-label">推送状态</span>
                  <el-tag :type="getSuggestionPushStatusMeta(item.push_status).tagType" size="small">
                    {{ getSuggestionPushStatusMeta(item.push_status).label }}
                  </el-tag>
                </div>
                <div class="status-row">
                  <span class="status-label">推送阻塞</span>
                  <span class="status-value">{{ item.push_blocker || '-' }}</span>
                </div>
                <div class="status-row">
                  <span class="status-label">采购单号</span>
                  <span class="status-value">{{ item.saihu_po_number || '-' }}</span>
                </div>
                <div class="status-row">
                  <span class="status-label">失败原因</span>
                  <span class="status-value">{{ item.push_error || '-' }}</span>
                </div>
              </div>
            </div>

            <div class="section action-row">
              <el-button
                type="primary"
                size="small"
                :loading="savingState[item.id] || false"
                :disabled="!isEditable(item) || !hasChanges(item)"
                @click="save(item)"
              >
                保存修改
              </el-button>
              <el-tag v-if="!isEditable(item)" type="info" style="margin-left: 12px">
                {{ item.push_status === 'pushed' ? '已推送条目不可编辑' : '已归档建议单不可编辑' }}
              </el-tag>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <el-empty v-else-if="notFound" description="建议单不存在或已失效。" :image-size="84">
      <el-button type="primary" @click="goCurrent">返回当前建议</el-button>
    </el-empty>

    <el-empty v-else-if="loadError" :description="loadError" :image-size="84">
      <el-button type="primary" @click="load">重新加载</el-button>
    </el-empty>

    <div v-else class="loading">加载中...</div>
  </div>
</template>

<script setup lang="ts">
import {
  getSuggestion,
  patchSuggestionItem,
  type AllocationExplanation,
  type SuggestionDetail,
  type SuggestionItem,
} from '@/api/suggestion'
import SkuCard from '@/components/SkuCard.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { allocationModeLabel, allocationModeTagType, allocationSummary } from '@/utils/allocation'
import { getSuggestionPushStatusMeta, getSuggestionStatusMeta } from '@/utils/status'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const suggestion = ref<SuggestionDetail | null>(null)
const expanded = ref<number[]>([])
const editing = reactive<Record<number, { total_qty: number }>>({})
const savingState = reactive<Record<number, boolean>>({})
const loading = ref(false)
const notFound = ref(false)
const loadError = ref('')

const suggestionStatusMeta = computed(() =>
  suggestion.value ? getSuggestionStatusMeta(suggestion.value.status) : { label: '暂无', tagType: 'info' as const },
)

const triggeredByLabel = computed(() => {
  if (!suggestion.value) return '-'
  return suggestion.value.triggered_by === 'manual' ? '手动触发' : '自动触发'
})

async function load(): Promise<void> {
  loading.value = true
  notFound.value = false
  loadError.value = ''

  const id = parsePositiveInt(route.params.id)
  if (!id) {
    suggestion.value = null
    notFound.value = true
    loading.value = false
    return
  }

  try {
    const data = await getSuggestion(id)
    suggestion.value = data
    syncEditingState(data)
    await syncRouteItemFocus(data)
  } catch (error) {
    suggestion.value = null
    const status = (error as { response?: { status?: number } })?.response?.status
    if (status === 404) {
      notFound.value = true
    } else {
      loadError.value = getActionErrorMessage(error, '加载建议详情失败。')
    }
  } finally {
    loading.value = false
  }
}

interface CountryRow {
  country: string
  qty: number
  warehouses: Record<string, number>
  allocation: AllocationExplanation | null
  t_purchase: string
  t_ship: string
}

function countryRows(item: SuggestionItem): CountryRow[] {
  return Object.entries(item.country_breakdown).map(([country, qty]) => ({
    country,
    qty,
    warehouses: item.warehouse_breakdown[country] || {},
    allocation: item.allocation_snapshot?.[country] || null,
    t_purchase: item.t_purchase[country] || '-',
    t_ship: item.t_ship[country] || '-',
  }))
}

function hasChanges(item: SuggestionItem): boolean {
  return editing[item.id]?.total_qty !== item.total_qty
}

function isEditable(item: SuggestionItem): boolean {
  return suggestion.value?.status !== 'archived' && item.push_status !== 'pushed'
}

async function save(item: SuggestionItem): Promise<void> {
  if (!suggestion.value || !isEditable(item)) return
  savingState[item.id] = true
  try {
    await patchSuggestionItem(suggestion.value.id, item.id, {
      total_qty: editing[item.id].total_qty,
    })
    await load()
    ElMessage.success('已保存，详情已刷新。')
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '保存失败。'))
  } finally {
    savingState[item.id] = false
  }
}

function formatDateTime(value?: string | null): string {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '-'
}

function parsePositiveInt(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function syncEditingState(data: SuggestionDetail): void {
  const activeIds = new Set(data.items.map((item) => item.id))
  for (const key of Object.keys(editing)) {
    const id = Number(key)
    if (!activeIds.has(id)) {
      delete editing[id]
      delete savingState[id]
    }
  }
  for (const item of data.items) {
    editing[item.id] = { total_qty: item.total_qty }
  }
}

async function syncRouteItemFocus(data: SuggestionDetail): Promise<void> {
  const itemId = parsePositiveInt(route.query.item)
  if (!itemId || !data.items.some((item) => item.id === itemId)) return

  if (!expanded.value.includes(itemId)) {
    expanded.value = [...expanded.value, itemId]
  }

  await nextTick()
  document.getElementById(`suggestion-item-${itemId}`)?.scrollIntoView({
    behavior: 'smooth',
    block: 'center',
  })
}

function goBack(): void {
  if (typeof window !== 'undefined' && window.history.length > 1) {
    router.back()
    return
  }
  router.push('/replenishment/current')
}

function goCurrent(): void {
  router.push('/replenishment/current')
}

watch(
  () => [route.params.id, route.query.item],
  () => {
    void load()
  },
  { immediate: true },
)
</script>

<style lang="scss" scoped>
.detail-view {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.header-main {
  display: flex;
  flex-direction: column;
  gap: $space-2;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-4;
}

.summary-meta {
  display: flex;
  flex-wrap: wrap;
  gap: $space-2;
}

.summary-chip {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: $radius-pill;
  background: $color-bg-subtle;
  color: $color-text-secondary;
  font-size: $font-size-xs;
}

.title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding-right: 24px;
}

.item-stats {
  display: flex;
  flex-direction: column;
  align-items: flex-end;

  .stat-label {
    color: $color-text-secondary;
    font-size: $font-size-xs;
  }

  strong {
    color: $color-brand-primary;
    font-size: $font-size-xl;
  }
}

.item-body {
  padding: $space-4 $space-2;
}

.section {
  margin-bottom: $space-5;
}

.action-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: $space-3;
}

.section-title {
  font-weight: $font-weight-medium;
  color: $color-text-secondary;
  margin-bottom: $space-2;
}

.warehouse-chip {
  display: inline-block;
  padding: 2px 8px;
  margin-right: 8px;
  background: $color-brand-primary-soft;
  color: $color-brand-primary;
  border-radius: $radius-pill;
  font-size: $font-size-xs;
}

.allocation-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px 0;
}

.allocation-text {
  color: $color-text-secondary;
  font-size: $font-size-xs;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: $space-3;
}

.status-row {
  display: flex;
  align-items: flex-start;
  gap: $space-3;
  min-width: 0;
}

.status-label {
  width: 72px;
  flex-shrink: 0;
  color: $color-text-secondary;
  font-size: $font-size-xs;
}

.status-value {
  min-width: 0;
  color: $color-text-primary;
  font-size: $font-size-sm;
  word-break: break-word;
}

.loading {
  text-align: center;
  padding: $space-12;
  color: $color-text-secondary;
}

@media (max-width: 900px) {
  .header-row,
  .item-header {
    flex-direction: column;
    align-items: flex-start;
    gap: $space-3;
  }

  .status-grid {
    grid-template-columns: 1fr;
  }
}
</style>
