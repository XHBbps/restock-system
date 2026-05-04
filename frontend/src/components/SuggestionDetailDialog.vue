<template>
  <el-dialog
    :model-value="modelValue"
    :title="dialogTitle"
    width="80%"
    :top="isEmptyState ? '' : '0'"
    :align-center="isEmptyState"
    :fullscreen="isMobile"
    :class="[
      'suggestion-detail-dialog',
      { 'suggestion-detail-dialog--empty': isEmptyState },
    ]"
    :close-on-click-modal="false"
    :show-close="false"
    @update:model-value="(value: boolean) => emit('update:modelValue', value)"
    @closed="reset"
  >
    <template #header="{ titleId, titleClass }">
      <div class="detail-dialog-header">
        <span :id="titleId" :class="titleClass" class="detail-dialog-header__title">
          {{ dialogTitle }}
        </span>
        <div class="detail-dialog-header__actions">
          <el-button
            v-if="currentSnapshot"
            type="primary"
            size="small"
            :loading="downloading"
            @click="download"
          >
            下载 Excel
          </el-button>
          <button
            type="button"
            class="dialog-close-btn"
            aria-label="关闭"
            @click="closeDialog"
          >
            <X :size="16" />
          </button>
        </div>
      </div>
    </template>

    <div v-loading="loadingList" class="detail-dialog-shell">
      <div class="detail-dialog-body">
        <aside class="version-side">
          <div class="version-side__title">版本列表</div>
          <div class="version-side__list">
            <button
              v-for="snapshot in snapshots"
              :key="snapshot.id"
              type="button"
              class="version-item"
              :class="{ 'version-item--active': currentSnapshotId === snapshot.id }"
              @click="selectSnapshot(snapshot.id)"
            >
              <div class="version-item__head">
                <span class="version-item__ver">V{{ snapshot.version }}</span>
                <span class="version-item__count">{{ snapshot.item_count }} 条</span>
              </div>
              <div class="version-item__time">{{ formatDateTime(snapshot.exported_at) }}</div>
            </button>
            <div v-if="snapshots.length === 0 && !loadingList" class="version-side__empty">
              暂无快照版本
            </div>
          </div>
        </aside>

        <section class="detail-main">
          <div v-if="!currentSnapshot" class="detail-main__empty">
            选择左侧版本查看详情
          </div>

          <template v-else>
            <dl class="detail-meta">
              <div class="detail-meta__row">
                <dt>版本</dt>
                <dd class="version-pill">V{{ currentSnapshot.version }}</dd>
                <dt>导出时间</dt>
                <dd>{{ formatDateTime(currentSnapshot.exported_at) }}</dd>
                <dt>导出人</dt>
                <dd>{{ currentSnapshot.exported_by_name || '-' }}</dd>
                <dt>补货日期</dt>
                <dd>{{ currentDemandDate || '-' }}</dd>
                <dt>条目数</dt>
                <dd>{{ currentSnapshot.item_count }}</dd>
              </div>
            </dl>

            <div class="detail-table-scroll">
              <el-table
                v-if="type === 'procurement'"
                v-loading="loadingDetail"
                :data="pagedItems"
                empty-text="该版本无条目"
                class="detail-table detail-table--procurement"
                height="100%"
              >
                <el-table-column label="商品信息" min-width="280">
                  <template #default="{ row }">
                    <SkuCard :sku="row.commodity_sku" :name="row.commodity_name" :image="row.main_image_url" />
                  </template>
                </el-table-column>
                <el-table-column label="采购量" prop="purchase_qty" width="110" align="right" />
              </el-table>

              <el-table
                v-else
                v-loading="loadingDetail"
                :data="pagedItems"
                empty-text="该版本无条目"
                class="detail-table detail-table--restock"
                height="100%"
              >
                <el-table-column type="expand" width="48">
                  <template #default="{ row }">
                    <div class="breakdown-table-scroll">
                      <table class="breakdown-table">
                        <thead>
                          <tr>
                            <th class="breakdown-col-country">国家</th>
                            <th class="breakdown-col-qty">补货量</th>
                            <th class="breakdown-col-warehouses">仓库分配</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr
                            v-for="country in itemCountryRows(row)"
                            :key="country.country"
                            class="breakdown-row"
                          >
                            <td class="breakdown-col-country">
                              <span class="breakdown-country-label">{{ getCountryLabel(country.country) }}</span>
                            </td>
                            <td class="breakdown-col-qty">
                              <span class="breakdown-qty-value">{{ country.qty }}</span>
                            </td>
                            <td class="breakdown-col-warehouses">
                              <template v-if="country.warehouses.length > 0">
                                <el-tag
                                  v-for="warehouse in country.warehouses"
                                  :key="warehouse.id"
                                  size="small"
                                  class="breakdown-warehouse-chip"
                                >
                                  {{ warehouseLabel(warehouse.id) }} · {{ warehouse.qty }}
                                </el-tag>
                              </template>
                              <el-tag v-else type="warning" effect="plain" size="small">
                                ⚠ 未拆仓（{{ country.qty }} 件待分配）
                              </el-tag>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="商品信息" min-width="280">
                  <template #default="{ row }">
                    <SkuCard :sku="row.commodity_sku" :name="row.commodity_name" :image="row.main_image_url" />
                  </template>
                </el-table-column>
                <el-table-column label="补货量" prop="total_qty" width="110" align="right" />
                <el-table-column label="国家分布" min-width="220">
                  <template #default="{ row }">
                    <div class="country-chips">
                      <el-tag
                        v-for="country in itemCountryRows(row)"
                        :key="country.country"
                        size="small"
                      >
                        {{ country.country }}: {{ country.qty }}
                      </el-tag>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <TablePaginationBar
              v-if="currentSnapshotTotal > 0"
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :total="currentSnapshotTotal"
              :page-sizes="pageSizeOptions"
              class="detail-pagination"
              @size-change="handlePageSizeChange"
            />
          </template>
        </section>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { listWarehouses, type Warehouse } from '@/api/config'
import {
  downloadSnapshotBlob,
  getSnapshot,
  listSnapshots,
  type SnapshotDetailOut,
  type SnapshotItemOut,
  type SnapshotOut,
  type SnapshotType,
} from '@/api/snapshot'
import SkuCard from '@/components/SkuCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { useResponsive } from '@/composables/useResponsive'
import { getActionErrorMessage } from '@/utils/apiError'
import { getCountryLabel } from '@/utils/countries'
import { triggerBlobDownload } from '@/utils/download'
import { clampPage, formatDateTime } from '@/utils/format'
import { ElMessage } from 'element-plus'
import { X } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  modelValue: boolean
  suggestionId: number | null
  type: SnapshotType
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const { isMobile } = useResponsive()
const snapshots = ref<SnapshotOut[]>([])
const currentSnapshot = ref<SnapshotDetailOut | null>(null)
const currentSnapshotId = ref<number | null>(null)
const loadingList = ref(false)
const loadingDetail = ref(false)
const downloading = ref(false)
const warehouseMap = ref<Record<string, string>>({})
const currentPage = ref(1)
const pageSize = ref(10)
const pageSizeOptions = [10, 20, 50, 100]

const dialogTitle = computed(() => {
  if (props.suggestionId === null) return '详情'
  const prefix = props.type === 'procurement' ? '采购建议单 CG-' : '补货建议单 BH-'
  return `${prefix}${props.suggestionId} 详情`
})
const isEmptyState = computed(
  () => !loadingList.value && !loadingDetail.value && currentSnapshot.value === null,
)

const currentItems = computed(() => currentSnapshot.value?.items ?? [])
const currentSnapshotTotal = computed(
  () => currentSnapshot.value?.item_count ?? currentItems.value.length,
)
const currentDemandDate = computed(() => {
  const value = currentSnapshot.value?.global_config_snapshot?.demand_date
  return typeof value === 'string' && value ? value : ''
})
const pagedItems = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return currentItems.value.slice(start, start + pageSize.value)
})

function warehouseLabel(warehouseId: string): string {
  const name = warehouseMap.value[warehouseId]
  return name ? `${name} (${warehouseId})` : warehouseId
}

interface CountryRow {
  country: string
  qty: number
  warehouses: { id: string; qty: number }[]
}

function itemCountryRows(item: SnapshotItemOut): CountryRow[] {
  const countryBreakdown = (item.country_breakdown || {}) as Record<string, number>
  const warehouseBreakdown = (item.warehouse_breakdown || {}) as Record<string, Record<string, number>>
  return Object.entries(countryBreakdown)
    .filter(([, qty]) => Number(qty) > 0)
    .map(([country, qty]) => ({
      country,
      qty: Number(qty),
      warehouses: Object.entries(warehouseBreakdown[country] || {})
        .filter(([, warehouseQty]) => Number(warehouseQty) > 0)
        .map(([id, warehouseQty]) => ({ id, qty: Number(warehouseQty) })),
    }))
}

async function loadWarehouses(): Promise<void> {
  if (Object.keys(warehouseMap.value).length > 0) return
  try {
    const rows = await listWarehouses()
    const map: Record<string, string> = {}
    for (const warehouse of rows as Warehouse[]) {
      map[warehouse.id] = warehouse.name
    }
    warehouseMap.value = map
  } catch {
    // 静默失败即可
  }
}

async function loadList(): Promise<void> {
  if (props.suggestionId === null) return
  loadingList.value = true
  try {
    const rows = await listSnapshots(props.suggestionId, props.type)
    snapshots.value = [...rows].sort((left, right) => right.version - left.version)
    if (snapshots.value.length > 0) {
      await selectSnapshot(snapshots.value[0].id)
      return
    }
    currentSnapshot.value = null
    currentSnapshotId.value = null
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '加载版本列表失败'))
  } finally {
    loadingList.value = false
  }
}

async function selectSnapshot(snapshotId: number): Promise<void> {
  resetCurrentPage()
  currentSnapshotId.value = snapshotId
  loadingDetail.value = true
  try {
    currentSnapshot.value = await getSnapshot(snapshotId)
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '加载版本详情失败'))
    currentSnapshot.value = null
  } finally {
    loadingDetail.value = false
  }
}

async function download(): Promise<void> {
  if (!currentSnapshot.value) return
  downloading.value = true
  try {
    const { blob, filename } = await downloadSnapshotBlob(currentSnapshot.value.id)
    triggerBlobDownload(blob, filename)
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '下载失败'))
  } finally {
    downloading.value = false
  }
}

function resetCurrentPage(): void {
  currentPage.value = 1
}

function resetPaginationState(): void {
  currentPage.value = 1
  pageSize.value = 10
}

function handlePageSizeChange(): void {
  currentPage.value = 1
}

function reset(): void {
  snapshots.value = []
  currentSnapshot.value = null
  currentSnapshotId.value = null
  resetPaginationState()
}

function closeDialog(): void {
  emit('update:modelValue', false)
}

watch(
  () => [props.modelValue, props.suggestionId, props.type] as const,
  ([open, suggestionId]) => {
    if (open && suggestionId !== null) {
      resetCurrentPage()
      void loadWarehouses()
      void loadList()
    }
  },
  { immediate: true },
)

watch(
  () => [currentSnapshotTotal.value, pageSize.value] as const,
  ([total, nextPageSize]) => {
    currentPage.value = clampPage(currentPage.value, total, nextPageSize)
  },
)
</script>

<style scoped lang="scss">
:global(.suggestion-detail-dialog) {
  display: flex;
  flex-direction: column;
  width: min(1280px, calc(100vw - 32px));
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 32px);
  margin: 16px auto !important;
}

:global(.suggestion-detail-dialog.suggestion-detail-dialog--empty) {
  margin: auto !important;
}

:global(.suggestion-detail-dialog .el-dialog__body) {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.detail-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $space-3;

  &__title {
    font-size: $font-size-lg;
    font-weight: $font-weight-semibold;
    color: $color-text-primary;
  }

  &__actions {
    display: flex;
    align-items: center;
    gap: $space-3;
    flex-shrink: 0;
  }
}

.dialog-close-btn {
  all: unset;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: $radius-md;
  color: $color-text-secondary;
  transition: $transition-fast;

  &:hover {
    background: $color-bg-subtle;
    color: $color-text-primary;
  }

  &:focus-visible {
    outline: 2px solid $color-brand-primary;
    outline-offset: 2px;
  }
}

.detail-dialog-shell {
  display: flex;
  flex: 1;
  min-height: 0;
  width: 100%;
  overflow: hidden;
}

.detail-dialog-body {
  display: grid;
  flex: 1;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: $space-4;
  min-height: 0;
  width: 100%;
  overflow: hidden;
}

.version-side {
  display: flex;
  flex-direction: column;
  gap: $space-2;
  min-height: 0;
  padding-right: $space-4;
  border-right: 1px solid $color-border-subtle;
  overflow: hidden;

  &__title {
    padding: 0 $space-2;
    font-size: $font-size-sm;
    font-weight: $font-weight-semibold;
    color: $color-text-secondary;
  }

  &__list {
    display: flex;
    flex: 1;
    flex-direction: column;
    gap: $space-1;
    min-height: 0;
    overflow-x: hidden;
    overflow-y: auto;
    padding-right: $space-1;
  }

  &__empty {
    padding: $space-4 $space-2;
    color: $color-text-secondary;
    font-size: $font-size-sm;
    text-align: center;
  }
}

.version-item {
  all: unset;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: $space-2 $space-3;
  border: 1px solid transparent;
  border-radius: $radius-md;
  transition: $transition-fast;

  &:hover {
    background: $color-bg-subtle;
  }

  &--active {
    background: $color-bg-subtle;
    border-color: $color-brand-primary;
  }

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: $space-2;
  }

  &__ver {
    font-family: $font-family-mono;
    font-weight: $font-weight-semibold;
    color: $color-brand-primary;
  }

  &__count,
  &__time {
    font-size: $font-size-xs;
    color: $color-text-secondary;
  }

  &__time {
    font-family: $font-family-mono;
  }
}

.detail-main {
  display: flex;
  flex-direction: column;
  gap: $space-4;
  min-width: 0;
  min-height: 0;
  overflow: hidden;

  &__empty {
    display: flex;
    flex: 1;
    align-items: center;
    justify-content: center;
    padding: $space-10 0;
    color: $color-text-secondary;
    text-align: center;
  }
}

.detail-meta {
  margin: 0;
  padding: $space-3 $space-4;
  background: $color-bg-subtle;
  border-radius: $radius-md;
  flex-shrink: 0;

  &__row {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto minmax(0, 1fr);
    column-gap: $space-3;
    row-gap: $space-2;
    align-items: center;

    dt {
      font-size: $font-size-xs;
      color: $color-text-secondary;
    }

    dd {
      margin: 0;
      font-size: $font-size-sm;
      color: $color-text-primary;
      word-break: break-word;
    }
  }
}

.version-pill {
  font-family: $font-family-mono !important;
  font-weight: $font-weight-semibold !important;
  color: $color-brand-primary !important;
}

.detail-table-scroll {
  position: relative;
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: auto;
}

.detail-table {
  flex: 1;
  min-width: 100%;
  min-height: 0;
}

.detail-pagination {
  flex-shrink: 0;
}

:deep(.detail-table .el-table__inner-wrapper) {
  min-height: 100%;
}

:deep(.detail-table .el-scrollbar__wrap),
:deep(.detail-table .el-table__body-wrapper) {
  overflow: auto;
}

.breakdown-table-scroll {
  overflow-x: auto;
  padding: $space-3 $space-4;
}

.breakdown-table {
  width: max-content;
  min-width: 100%;
  margin: 0;
  border-collapse: separate;
  border-spacing: 0;
  background: $color-bg-subtle;
  border: 1px solid $color-border-subtle;
  border-radius: $radius-md;
  overflow: hidden;

  th,
  td {
    padding: $space-2 $space-3;
    text-align: left;
    vertical-align: middle;
  }

  thead th {
    font-size: $font-size-xs;
    font-weight: 600;
    color: $color-text-secondary;
    background: $color-bg-base;
    border-bottom: 1px solid $color-border-subtle;
  }

  .breakdown-row + .breakdown-row td {
    border-top: 1px dashed $color-border-subtle;
  }
}

.breakdown-col-country {
  width: 180px;
}

.breakdown-col-qty {
  width: 110px;
  text-align: right !important;
}

.breakdown-col-warehouses {
  min-width: 320px;
}

.breakdown-country-label {
  font-weight: 600;
  color: $color-text-primary;
}

.breakdown-qty-value {
  font-family: $font-family-mono;
  font-weight: 600;
  color: $color-brand-primary;
}

.breakdown-warehouse-chip {
  margin: 2px 4px 2px 0;
}

.country-chips {
  display: flex;
  flex-wrap: wrap;
  gap: $space-2;
}

@media (max-width: 1200px) {
  .detail-dialog-body {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto minmax(0, 1fr);
  }

  .version-side {
    padding-right: 0;
    padding-bottom: $space-3;
    border-right: 0;
    border-bottom: 1px solid $color-border-subtle;
  }

  .version-side__list {
    flex-direction: row;
    overflow-x: auto;
    overflow-y: hidden;
    padding-right: 0;
    padding-bottom: $space-1;
  }

  .version-item {
    flex: 0 0 180px;
    min-width: 180px;
  }
}

@media (max-width: 767px) {
  :global(.suggestion-detail-dialog) {
    width: 100vw !important;
    max-width: 100vw;
    height: 100vh;
    max-height: 100vh;
    margin: 0 !important;
  }

  :global(.suggestion-detail-dialog .el-dialog__header) {
    padding: $space-3 $space-4;
  }

  :global(.suggestion-detail-dialog .el-dialog__body) {
    flex: 1;
    max-height: none;
    padding: $space-3;
    overflow: hidden;
  }

  .detail-dialog-header {
    align-items: flex-start;

    &__title {
      min-width: 0;
      font-size: $font-size-sm;
      line-height: $line-height-snug;
    }

    &__actions {
      gap: $space-2;
    }
  }

  .detail-dialog-body {
    grid-template-rows: auto minmax(0, 1fr);
    gap: $space-3;
  }

  .version-side {
    max-height: 112px;
    padding-bottom: $space-2;
  }

  .version-side__title {
    font-size: $font-size-xs;
  }

  .version-item {
    flex-basis: 156px;
    min-width: 156px;
    padding: $space-2;
  }

  .detail-main {
    gap: $space-3;
  }

  .detail-meta__row {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .detail-table-scroll {
    min-height: 260px;
  }

  .breakdown-col-country {
    width: 140px;
  }

  .breakdown-col-warehouses {
    min-width: 260px;
  }
}
</style>
