<template>
  <el-dialog
    :model-value="modelValue"
    :title="dialogTitle"
    width="80%"
    :close-on-click-modal="false"
    :show-close="false"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
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

    <div v-loading="loadingList" class="detail-dialog-body">
      <!-- 左侧：版本切换 -->
      <aside class="version-side">
        <div class="version-side__title">版本列表</div>
        <div class="version-side__list">
          <button
            v-for="snap in snapshots"
            :key="snap.id"
            type="button"
            class="version-item"
            :class="{ 'version-item--active': currentSnapshotId === snap.id }"
            @click="selectSnapshot(snap.id)"
          >
            <div class="version-item__head">
              <span class="version-item__ver">V{{ snap.version }}</span>
              <span class="version-item__count">{{ snap.item_count }} 条</span>
            </div>
            <div class="version-item__time">{{ formatDateTime(snap.exported_at) }}</div>
          </button>
          <div v-if="snapshots.length === 0 && !loadingList" class="version-side__empty">
            暂无快照版本
          </div>
        </div>
      </aside>

      <!-- 右侧：主内容 -->
      <section class="detail-main">
        <div v-if="!currentSnapshot" class="detail-main__empty">
          选择左侧版本查看详情
        </div>

        <template v-else>
          <!-- 元数据 -->
          <dl class="detail-meta">
            <div class="detail-meta__row">
              <dt>版本</dt>
              <dd class="version-pill">V{{ currentSnapshot.version }}</dd>
              <dt>导出时间</dt>
              <dd>{{ formatDateTime(currentSnapshot.exported_at) }}</dd>
              <dt>导出人</dt>
              <dd>{{ currentSnapshot.exported_by_name || '-' }}</dd>
              <dt>条目数</dt>
              <dd>{{ currentSnapshot.item_count }}</dd>
            </div>
          </dl>

          <!-- 明细表格（分采购/补货） -->
          <el-table
            v-if="type === 'procurement'"
            v-loading="loadingDetail"
            :data="currentSnapshot.items"
            empty-text="该版本无条目"
            class="detail-table"
            max-height="500"
          >
            <el-table-column label="商品信息" min-width="280">
              <template #default="{ row }">
                <SkuCard :sku="row.commodity_sku" :name="row.commodity_name" :image="row.main_image_url" />
              </template>
            </el-table-column>
            <el-table-column label="采购量" prop="purchase_qty" width="110" align="right" />
            <el-table-column label="采购日期" width="180">
              <template #default="{ row }">
                <PurchaseDateCell :date="row.purchase_date" />
              </template>
            </el-table-column>
          </el-table>

          <el-table
            v-else
            v-loading="loadingDetail"
            :data="currentSnapshot.items"
            empty-text="该版本无条目"
            class="detail-table"
            max-height="500"
          >
            <el-table-column type="expand" width="48">
              <template #default="{ row }">
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
                            v-for="w in country.warehouses"
                            :key="w.id"
                            size="small"
                            class="breakdown-warehouse-chip"
                          >
                            {{ warehouseLabel(w.id) }} · {{ w.qty }}
                          </el-tag>
                        </template>
                        <el-tag v-else type="warning" effect="plain" size="small">
                          ⚠ 未拆仓（{{ country.qty }} 件待分配）
                        </el-tag>
                      </td>
                    </tr>
                  </tbody>
                </table>
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
        </template>
      </section>
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
import PurchaseDateCell from '@/components/PurchaseDateCell.vue'
import SkuCard from '@/components/SkuCard.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { getCountryLabel } from '@/utils/countries'
import { triggerBlobDownload } from '@/utils/download'
import { formatDateTime } from '@/utils/format'
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

const snapshots = ref<SnapshotOut[]>([])
const currentSnapshot = ref<SnapshotDetailOut | null>(null)
const currentSnapshotId = ref<number | null>(null)
const loadingList = ref(false)
const loadingDetail = ref(false)
const downloading = ref(false)
const warehouseMap = ref<Record<string, string>>({})

const dialogTitle = computed(() => {
  if (props.suggestionId === null) return '详情'
  const prefix = props.type === 'procurement' ? '采购建议单 CG-' : '补货建议单 BH-'
  return `${prefix}${props.suggestionId} 详情`
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
        .filter(([, wqty]) => Number(wqty) > 0)
        .map(([id, wqty]) => ({ id, qty: Number(wqty) })),
    }))
}

async function loadWarehouses(): Promise<void> {
  if (Object.keys(warehouseMap.value).length > 0) return
  try {
    const rows = await listWarehouses()
    const map: Record<string, string> = {}
    for (const w of rows as Warehouse[]) {
      map[w.id] = w.name
    }
    warehouseMap.value = map
  } catch {
    // 静默
  }
}

async function loadList(): Promise<void> {
  if (props.suggestionId === null) return
  loadingList.value = true
  try {
    const rows = await listSnapshots(props.suggestionId, props.type)
    // 按 version 降序（最新在上）
    snapshots.value = [...rows].sort((a, b) => b.version - a.version)
    if (snapshots.value.length > 0) {
      await selectSnapshot(snapshots.value[0].id)
    } else {
      currentSnapshot.value = null
      currentSnapshotId.value = null
    }
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '加载版本列表失败'))
  } finally {
    loadingList.value = false
  }
}

async function selectSnapshot(snapshotId: number): Promise<void> {
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

function reset(): void {
  snapshots.value = []
  currentSnapshot.value = null
  currentSnapshotId.value = null
}

function closeDialog(): void {
  emit('update:modelValue', false)
}

watch(
  () => [props.modelValue, props.suggestionId] as const,
  ([open, id]) => {
    if (open && id !== null) {
      void loadWarehouses()
      void loadList()
    }
  },
  { immediate: true },
)
</script>

<style scoped lang="scss">
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
    gap: $space-3;    // 下载按钮和 × 间隔
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

.detail-dialog-body {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: $space-4;
  min-height: 500px;
}

// ========== 版本列表（左侧） ==========
.version-side {
  display: flex;
  flex-direction: column;
  gap: $space-2;
  border-right: 1px solid $color-border-subtle;
  padding-right: $space-4;

  &__title {
    font-size: $font-size-sm;
    font-weight: $font-weight-semibold;
    color: $color-text-secondary;
    padding: 0 $space-2;
  }

  &__list {
    display: flex;
    flex-direction: column;
    gap: $space-1;
    max-height: 560px;   // 固定高度，多版本时独立滚动
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
  border-radius: $radius-md;
  transition: $transition-fast;
  border: 1px solid transparent;

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
  }

  &__ver {
    font-family: $font-family-mono;
    font-weight: $font-weight-semibold;
    color: $color-brand-primary;
  }

  &__count {
    font-size: $font-size-xs;
    color: $color-text-secondary;
  }

  &__time {
    font-size: $font-size-xs;
    color: $color-text-secondary;
    font-family: $font-family-mono;
  }
}

// ========== 主内容（右侧） ==========
.detail-main {
  display: flex;
  flex-direction: column;
  gap: $space-4;
  min-height: 0;

  &__empty {
    padding: $space-10 0;
    text-align: center;
    color: $color-text-secondary;
  }
}

.detail-meta {
  padding: $space-3 $space-4;
  background: $color-bg-subtle;
  border-radius: $radius-md;
  margin: 0;

  &__row {
    display: grid;
    grid-template-columns: auto 1fr auto 1fr;
    row-gap: $space-2;
    column-gap: $space-3;
    align-items: center;

    dt {
      font-size: $font-size-xs;
      color: $color-text-secondary;
    }

    dd {
      margin: 0;
      font-size: $font-size-sm;
      color: $color-text-primary;
    }
  }
}

.version-pill {
  font-family: $font-family-mono !important;
  font-weight: $font-weight-semibold !important;
  color: $color-brand-primary !important;
}

.detail-table {
  flex: 1;
  min-height: 0;
}

// 补货视图展开行样式（复用 RestockListView 设计）
.breakdown-table {
  width: 100%;
  margin: $space-3 $space-4;
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
</style>
