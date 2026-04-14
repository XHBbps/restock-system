<template>
  <div class="detail-view">
    <el-card v-if="suggestion" v-loading="loading" shadow="never">
      <template #header>
        <div class="header-row">
          <div class="header-main">
            <div class="title-row">
              <span class="title">建议单 #{{ suggestion.id }}</span>
              <el-tag :type="suggestionStatusMeta.tagType">
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

      <el-collapse v-model="expanded">
        <el-collapse-item v-for="item in suggestion.items" :key="item.id" :name="item.id">
          <template #title>
            <div :id="`suggestion-item-${item.id}`" class="item-header">
              <div class="item-main-header">
                <SkuCard
                  :sku="item.commodity_sku"
                  :name="item.commodity_name"
                  :image="item.main_image"
                  :blocker="item.push_blocker"
                />
              </div>
              <div class="item-stats">
                <span class="stat-label">总采购量</span>
                <strong>{{ item.total_qty }}</strong>
              </div>
            </div>
          </template>

          <div class="item-body">
            <div class="item-grid">
              <div class="item-main">
                <section class="panel panel-compact">
                  <div class="panel-header">
                    <div>
                      <div class="section-title">采购调整</div>
                      <div class="section-desc">可统一调整总量，并按国家与仓库逐项校正。</div>
                    </div>
                  </div>
                  <div class="editor-row">
                    <div class="editor-field">
                      <span class="editor-label">总采购量</span>
                      <el-input-number v-model="editing[item.id].total_qty" :min="0" size="small" />
                    </div>
                    <div class="editor-hint">国家补货量之和不要求等于总采购量；已配置仓库时，仓内分量之和必须等于国家补货量。</div>
                  </div>
                </section>

                <section class="panel">
                  <div class="panel-header">
                    <div>
                      <div class="section-title">国家补货量与仓内拆分</div>
                    </div>
                  </div>
                  <el-table :data="countryRows(item)" size="small" class="detail-table">
                    <el-table-column prop="country" label="国家" width="88" sortable show-overflow-tooltip />
                    <el-table-column label="国家补货量" width="140">
                      <template #default="{ row }">
                        <el-input-number
                          v-if="isEditable(item)"
                          v-model="editing[item.id].country_breakdown[row.country]"
                          :min="0"
                          class="table-number-input"
                          size="small"
                        />
                        <span v-else>{{ row.qty }}</span>
                      </template>
                    </el-table-column>
                    <el-table-column label="各仓明细" min-width="240">
                      <template #default="{ row }">
                        <div v-if="Object.keys(row.warehouses).length" class="warehouse-list">
                          <template v-for="(qty, warehouseId) in row.warehouses" :key="warehouseId">
                            <label v-if="isEditable(item)" class="warehouse-editor">
                              <span class="warehouse-label">{{ warehouseId }}</span>
                              <el-input-number
                                v-model="editing[item.id].warehouse_breakdown[row.country][warehouseId]"
                                :min="0"
                                class="table-number-input warehouse-number-input"
                                size="small"
                              />
                            </label>
                            <span v-else class="warehouse-chip">{{ warehouseId }}: {{ qty }}</span>
                          </template>
                        </div>
                        <span v-else class="allocation-text">未拆分</span>
                      </template>
                    </el-table-column>
                    <el-table-column label="拆分依据" min-width="260">
                      <template #default="{ row }">
                        <div v-if="row.allocation" class="allocation-meta">
                          <div class="allocation-top">
                            <el-tag :type="allocationModeTagType(row.allocation.allocation_mode)" size="small">
                              {{ allocationModeLabel(row.allocation.allocation_mode) }}
                            </el-tag>
                            <span class="allocation-text">{{ allocationSummary(row.allocation) }}</span>
                          </div>
                          <span class="allocation-text">可用仓：{{ row.allocation.eligible_warehouses.join(', ') || '-' }}</span>
                        </div>
                        <span v-else class="allocation-text">-</span>
                      </template>
                    </el-table-column>
                  </el-table>
                </section>
              </div>

              <aside class="item-side">
                <section class="panel panel-side">
                  <div class="panel-header">
                    <div>
                      <div class="section-title">状态信息</div>
                      <div class="section-desc">用于快速判断当前条目的推送状态和异常信息。</div>
                    </div>
                  </div>
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
                </section>

                <section class="panel panel-side panel-action">
                  <div class="panel-header">
                    <div>
                      <div class="section-title">操作</div>
                      <div class="section-desc">保存本次采购调整。</div>
                    </div>
                  </div>
                  <div class="action-stack">
                    <el-button
                      type="primary"
                      size="small"
                      :loading="savingState[item.id] || false"
                      :disabled="!isEditable(item) || !hasChanges(item)"
                      @click="save(item)"
                    >
                      保存修改
                    </el-button>
                    <el-tag v-if="!isEditable(item)" type="info">
                      {{ item.push_status === 'pushed' ? '已推送条目不可编辑' : '已归档建议单不可编辑' }}
                    </el-tag>
                    <span v-else-if="!hasChanges(item)" class="action-hint">修改国家补货量或仓库分量后可保存</span>
                  </div>
                </section>
              </aside>
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
import { useAuthStore } from '@/stores/auth'
import { getActionErrorMessage } from '@/utils/apiError'
import { allocationModeLabel, allocationModeTagType, allocationSummary } from '@/utils/allocation'
import { getSuggestionPushStatusMeta, getSuggestionStatusMeta } from '@/utils/status'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

interface ItemEditingState {
  total_qty: number
  country_breakdown: Record<string, number>
  warehouse_breakdown: Record<string, Record<string, number>>
}

interface CountryRow {
  country: string
  qty: number
  warehouses: Record<string, number>
  allocation: AllocationExplanation | null
}

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const suggestion = ref<SuggestionDetail | null>(null)
const expanded = ref<number[]>([])
const editing = reactive<Record<number, ItemEditingState>>({})
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

function countryRows(item: SuggestionItem): CountryRow[] {
  const state = editing[item.id]
  const countries = collectCountries(item, state)
  return countries.map((country) => ({
    country,
    qty: state?.country_breakdown[country] ?? item.country_breakdown[country] ?? 0,
    warehouses: state?.warehouse_breakdown[country] ?? item.warehouse_breakdown[country] ?? {},
    allocation: item.allocation_snapshot?.[country] || null,
  }))
}

function hasChanges(item: SuggestionItem): boolean {
  const state = editing[item.id]
  if (!state) return false
  return JSON.stringify(normalizeEditingState(state)) !== JSON.stringify(snapshotItemState(item))
}

function isEditable(item: SuggestionItem): boolean {
  return suggestion.value?.status !== 'archived' && item.push_status !== 'pushed' && auth.hasPermission('restock:operate')
}

async function save(item: SuggestionItem): Promise<void> {
  if (!suggestion.value || !isEditable(item)) return
  const state = editing[item.id]
  const validationError = validateEditingState(item, state)
  if (validationError) {
    ElMessage.error(validationError)
    return
  }

  const patch = buildPatch(item, state)
  if (!Object.keys(patch).length) return

  savingState[item.id] = true
  try {
    await patchSuggestionItem(suggestion.value.id, item.id, patch)
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

function collectCountries(item: SuggestionItem, state?: ItemEditingState): string[] {
  return [
    ...new Set([
      ...Object.keys(item.country_breakdown || {}),
      ...Object.keys(item.warehouse_breakdown || {}),
      ...Object.keys(item.allocation_snapshot || {}),
      ...(state
        ? [
            ...Object.keys(state.country_breakdown),
            ...Object.keys(state.warehouse_breakdown),
          ]
        : []),
    ]),
  ].sort()
}

function normalizeNumberMap(input: Record<string, number>): Record<string, number> {
  return Object.fromEntries(
    Object.entries(input)
      .map(([key, value]) => [key, Number(value ?? 0)])
      .sort(([left], [right]) => String(left).localeCompare(String(right))),
  )
}

function normalizeWarehouseBreakdown(
  input: Record<string, Record<string, number>>,
): Record<string, Record<string, number>> {
  return Object.fromEntries(
    Object.entries(input)
      .map(([country, warehouses]) => [
        country,
        Object.fromEntries(
          Object.entries(warehouses)
            .map(([warehouseId, qty]) => [warehouseId, Number(qty ?? 0)])
            .sort(([left], [right]) => String(left).localeCompare(String(right))),
        ),
      ])
      .sort(([left], [right]) => left.localeCompare(right)),
  )
}

function normalizeEditingState(state: ItemEditingState) {
  return {
    total_qty: Number(state.total_qty ?? 0),
    country_breakdown: normalizeNumberMap(state.country_breakdown),
    warehouse_breakdown: normalizeWarehouseBreakdown(state.warehouse_breakdown),
  }
}

function snapshotItemState(item: SuggestionItem) {
  return normalizeEditingState({
    total_qty: item.total_qty,
    country_breakdown: item.country_breakdown,
    warehouse_breakdown: item.warehouse_breakdown,
  })
}

function buildPatch(item: SuggestionItem, state: ItemEditingState) {
  const patch: {
    total_qty?: number
    country_breakdown?: Record<string, number>
    warehouse_breakdown?: Record<string, Record<string, number>>
  } = {}
  const normalizedState = normalizeEditingState(state)
  const normalizedItem = snapshotItemState(item)

  if (normalizedState.total_qty !== normalizedItem.total_qty) {
    patch.total_qty = normalizedState.total_qty
  }
  if (JSON.stringify(normalizedState.country_breakdown) !== JSON.stringify(normalizedItem.country_breakdown)) {
    patch.country_breakdown = normalizedState.country_breakdown
  }
  if (JSON.stringify(normalizedState.warehouse_breakdown) !== JSON.stringify(normalizedItem.warehouse_breakdown)) {
    patch.warehouse_breakdown = normalizedState.warehouse_breakdown
  }

  return patch
}

function validateEditingState(item: SuggestionItem, state?: ItemEditingState): string | null {
  if (!state) return '编辑状态缺失，请刷新后重试。'

  for (const country of collectCountries(item, state)) {
    const countryQty = Number(state.country_breakdown[country] ?? 0)
    const warehouses = state.warehouse_breakdown[country] || {}
    const warehouseValues = Object.values(warehouses)
    if (!warehouseValues.length) continue

    const warehouseTotal = warehouseValues.reduce((sum, qty) => sum + Number(qty || 0), 0)
    if (warehouseTotal !== countryQty) {
      return `${country} 的各仓明细之和必须等于国家补货量。`
    }
  }

  return null
}

function syncEditingState(data: SuggestionDetail): void {
  const activeIds = new Set(data.items.map((item) => item.id))
  expanded.value = expanded.value.filter((itemId) => activeIds.has(itemId))

  for (const key of Object.keys(editing)) {
    const id = Number(key)
    if (!activeIds.has(id)) {
      delete editing[id]
      delete savingState[id]
    }
  }

  for (const item of data.items) {
    editing[item.id] = {
      total_qty: item.total_qty,
      country_breakdown: Object.fromEntries(
        Object.entries(item.country_breakdown).map(([country, qty]) => [country, Number(qty)]),
      ),
      warehouse_breakdown: Object.fromEntries(
        Object.entries(item.warehouse_breakdown).map(([country, warehouses]) => [
          country,
          Object.fromEntries(Object.entries(warehouses).map(([warehouseId, qty]) => [warehouseId, Number(qty)])),
        ]),
      ),
    }
  }
}

async function syncRouteItemFocus(data: SuggestionDetail): Promise<void> {
  const itemId = parsePositiveInt(route.query.item)
  if (!itemId || !data.items.some((item) => item.id === itemId)) return

  if (expanded.value.length !== 1 || expanded.value[0] !== itemId) {
    expanded.value = [itemId]
  }

  await nextTick()
  document.getElementById(`suggestion-item-${itemId}`)?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}

function goBack(): void {
  if (typeof window !== 'undefined' && window.history.length > 1) {
    router.back()
    return
  }
  router.push('/restock/current')
}

function goCurrent(): void {
  router.push('/restock/current')
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
  gap: $space-3;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-4;
}

.title-row {
  display: flex;
  align-items: center;
  gap: $space-3;
  flex-wrap: wrap;
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
  gap: $space-4;
  width: 100%;
  min-width: 0;
  padding-right: $space-3;
  scroll-margin-top: calc($layout-topbar-height + $space-6);
}

.item-main-header {
  flex: 1;
  min-width: 0;
}

.item-stats {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 96px;
  min-height: 64px;
  padding: $space-2;
  border-radius: $radius-lg;
  background: $color-bg-subtle;
  border: 1px solid $color-border-default;

  .stat-label {
    color: $color-text-secondary;
    font-size: $font-size-xs;
    line-height: 1.2;
  }

  strong {
    color: $color-text-primary;
    font-size: 22px;
    line-height: 1.1;
  }
}

.item-body {
  padding: $space-4 0 $space-2;
}

.item-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: $space-4;
  align-items: start;
}

.item-main,
.item-side {
  display: flex;
  flex-direction: column;
  gap: $space-3;
}

.panel {
  border: 1px solid $color-border-default;
  border-radius: $radius-lg;
  background: $color-bg-card;
  padding: $space-4;
}

.panel-compact {
  padding-bottom: $space-3;
}

.panel-side {
  background: $color-bg-subtle;
}

.panel-action {
  position: sticky;
  top: calc($layout-topbar-height + $space-4);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: $space-3;
  margin-bottom: $space-3;
}

.section-title {
  font-weight: $font-weight-medium;
  color: $color-text-primary;
}

.section-desc {
  margin-top: 4px;
  color: $color-text-secondary;
  font-size: $font-size-xs;
  line-height: 1.5;
}

.editor-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-4;
  flex-wrap: wrap;
}

.editor-field {
  display: flex;
  align-items: center;
  gap: $space-3;
}

.editor-label {
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.editor-hint {
  color: $color-text-secondary;
  font-size: $font-size-xs;
  line-height: 1.5;
  text-align: right;
}

.warehouse-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  background: $color-brand-primary-soft;
  color: $color-brand-primary;
  border-radius: $radius-pill;
  font-size: $font-size-xs;
}

.warehouse-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.warehouse-editor {
  display: grid;
  grid-template-columns: minmax(48px, max-content) minmax(0, 1fr);
  align-items: center;
  gap: 6px;
  width: 100%;
  min-width: 0;
}

.warehouse-label {
  min-width: 0;
  color: $color-text-secondary;
  font-size: $font-size-xs;
  overflow-wrap: anywhere;
}

.allocation-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px 0;
}

.allocation-top {
  display: flex;
  align-items: center;
  gap: $space-2;
  flex-wrap: wrap;
}

.allocation-text {
  color: $color-text-secondary;
  font-size: $font-size-xs;
  line-height: 1.5;
}

.status-grid {
  display: flex;
  flex-direction: column;
  gap: $space-3;
}

.status-row {
  display: flex;
  align-items: flex-start;
  gap: $space-3;
  min-width: 0;
  padding-bottom: $space-3;
  border-bottom: 1px solid $color-border-default;
}

.status-row:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.status-label {
  width: 76px;
  flex-shrink: 0;
  color: $color-text-secondary;
  font-size: $font-size-xs;
  line-height: 1.6;
}

.status-value {
  min-width: 0;
  flex: 1;
  color: $color-text-primary;
  font-size: $font-size-sm;
  line-height: 1.6;
  word-break: break-word;
}

.action-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: $space-3;
}

.action-hint {
  color: $color-text-secondary;
  font-size: $font-size-xs;
}

.loading {
  text-align: center;
  padding: $space-12;
  color: $color-text-secondary;
}

:deep(.el-collapse) {
  border-top: none;
  border-bottom: none;
}

:deep(.el-collapse-item) {
  margin-bottom: $space-3;
  border: 1px solid $color-border-default;
  border-radius: $radius-lg;
  overflow: hidden;
  background: $color-bg-card;
}

:deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

:deep(.el-collapse-item__header) {
  align-items: stretch;
  height: auto;
  min-height: 92px;
  line-height: normal;
  padding: $space-3 $space-4;
  background: $color-bg-card;
  border-bottom: 1px solid $color-border-default;
  overflow: visible;
}

:deep(.el-collapse-item__content) {
  padding-bottom: 0;
  background: $color-bg-card;
}

:deep(.el-collapse-item__arrow) {
  align-self: center;
  margin-left: $space-3;
}

:deep(.detail-table th.el-table__cell) {
  background: $color-bg-subtle;
}

:deep(.detail-table .cell) {
  line-height: 1.5;
  min-width: 0;
  overflow-wrap: anywhere;
}

:deep(.detail-table .table-number-input) {
  width: 100%;
  max-width: 116px;
}

:deep(.detail-table .warehouse-number-input) {
  max-width: 108px;
}

:deep(.sku-card) {
  flex: 1;
  min-width: 0;
  align-items: flex-start;
}

:deep(.sku-card .sku-meta) {
  min-width: 0;
}

:deep(.sku-card .sku-name) {
  display: -webkit-box;
  white-space: normal;
  word-break: break-word;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

:deep(.sku-card .sku-code) {
  word-break: break-all;
}

:deep(.sku-card .el-tag) {
  flex-shrink: 0;
}

@media (max-width: 900px) {
  .header-row,
  .item-header {
    flex-direction: column;
    align-items: flex-start;
    gap: $space-3;
  }

  .item-grid {
    grid-template-columns: 1fr;
  }

  .panel-action {
    position: static;
  }

  .item-stats {
    width: auto;
    min-width: 96px;
  }

  .editor-row,
  .status-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .editor-hint {
    text-align: left;
  }
}
</style>
