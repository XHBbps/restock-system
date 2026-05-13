<template>
  <el-empty
    v-if="suggestion?.procurement_item_count === 0"
    description="本期无采购需求"
    :image-size="80"
  />
  <div v-else class="procurement-list">
    <div class="table-toolbar">
      <div class="table-toolbar__filters">
        <el-input v-model="skuFilter" placeholder="SKU 搜索" clearable style="width: 220px" />
      </div>
      <div class="table-toolbar__actions">
        <el-checkbox
          v-if="editable && isMobile"
          :model-value="isAllSelected"
          :indeterminate="isIndeterminate"
          :disabled="allSelectableIds.length === 0"
          @change="(checked: string | number | boolean) => toggleSelectAll(Boolean(checked))"
        >
          全选
        </el-checkbox>
        <el-button
          v-if="editable"
          type="primary"
          :disabled="selectedCount === 0"
          :loading="exporting"
          @click="handleExport"
        >
          {{ exportButtonLabel }}
        </el-button>
      </div>
    </div>

    <el-table
      v-if="!isMobile"
      v-loading="loading"
      :data="pagedItems"
      empty-text="本期无采购需求"
    >
      <el-table-column v-if="editable" width="56" align="center">
        <template #header>
          <el-checkbox
            :model-value="isAllSelected"
            :indeterminate="isIndeterminate"
            :disabled="allSelectableIds.length === 0"
            @change="(checked: string | number | boolean) => toggleSelectAll(Boolean(checked))"
          />
        </template>
        <template #default="{ row }">
          <el-checkbox
            :model-value="isRowSelected(row.id)"
            @change="(checked: string | number | boolean) => toggleRow(row.id, Boolean(checked))"
          />
        </template>
      </el-table-column>
      <el-table-column type="expand" width="48">
        <template #default="{ row }">
          <ProcurementCalculationPanel :item="row" />
        </template>
      </el-table-column>
      <el-table-column label="商品信息" min-width="260">
        <template #default="{ row }">
          <SkuCard :sku="row.commodity_sku" :name="row.commodity_name" :image="row.main_image" />
        </template>
      </el-table-column>
      <el-table-column label="采购量" prop="purchase_qty" width="150" align="right">
        <template #default="{ row }">
          <el-input-number
            v-if="editable"
            :model-value="draftValue(row.id, 'purchase_qty', row.purchase_qty)"
            :min="0"
            size="small"
            @update:model-value="
              (value: number | undefined) => updateDraft(row.id, 'purchase_qty', Number(value ?? 0))
            "
          />
          <span v-else>{{ row.purchase_qty }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.procurement_export_status === 'exported' ? 'success' : 'warning'" size="small">
            {{ row.procurement_export_status === 'exported' ? '已导出' : '未导出' }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>

    <MobileRecordList
      v-else
      :items="pagedItems"
      :loading="loading"
      row-key="id"
      empty-text="本期无采购需求"
    >
      <template #default="{ item: row }">
        <div class="mobile-suggestion-card">
          <div class="mobile-suggestion-card__head">
            <el-checkbox
              v-if="editable"
              :model-value="isRowSelected(row.id)"
              @change="(checked: string | number | boolean) => toggleRow(row.id, Boolean(checked))"
            />
            <SkuCard :sku="row.commodity_sku" :name="row.commodity_name" :image="row.main_image" />
          </div>
          <div class="mobile-suggestion-card__body">
            <div class="mobile-field">
              <span>采购量</span>
              <el-input-number
                v-if="editable"
                :model-value="draftValue(row.id, 'purchase_qty', row.purchase_qty)"
                :min="0"
                size="small"
                @update:model-value="
                  (value: number | undefined) => updateDraft(row.id, 'purchase_qty', Number(value ?? 0))
                "
              />
              <strong v-else>{{ row.purchase_qty }}</strong>
            </div>
            <div class="mobile-field">
              <span>状态</span>
              <el-tag :type="row.procurement_export_status === 'exported' ? 'success' : 'warning'" size="small">
                {{ row.procurement_export_status === 'exported' ? '已导出' : '未导出' }}
              </el-tag>
            </div>
          </div>
          <ProcurementCalculationPanel :item="row" compact />
        </div>
      </template>
    </MobileRecordList>

    <TablePaginationBar
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="filteredItems.length"
      :page-sizes="[20, 50, 100, 200]"
      @size-change="page = 1"
    />
  </div>
</template>

<script setup lang="ts">
import {
  patchSuggestionItem,
  type SuggestionDetail,
  type SuggestionItem,
  type SuggestionItemPatch,
} from '@/api/suggestion'
import { createProcurementSnapshot, downloadSnapshotBlob } from '@/api/snapshot'
import MobileRecordList from '@/components/MobileRecordList.vue'
import SkuCard from '@/components/SkuCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { useResponsive } from '@/composables/useResponsive'
import { getActionErrorMessage } from '@/utils/apiError'
import { getCountryLabel } from '@/utils/countries'
import { triggerBlobDownload } from '@/utils/download'
import { useCrossPageSelection } from '@/views/suggestion/useCrossPageSelection'
import { ElMessage } from 'element-plus'
import { computed, defineComponent, h, ref, watch, type PropType } from 'vue'

const props = defineProps<{
  suggestion: SuggestionDetail | null
  items: SuggestionItem[]
  loading?: boolean
}>()

const emit = defineEmits<{
  refresh: []
}>()

const skuFilter = ref('')
const { isMobile } = useResponsive()
const page = ref(1)
const pageSize = ref(20)
const exporting = ref(false)
const draftPatches = ref<Record<number, SuggestionItemPatch>>({})

watch(skuFilter, () => {
  page.value = 1
})

const editable = computed(() => props.suggestion?.status === 'draft')

const procurementItems = computed(() =>
  props.items
    .filter((item) => item.purchase_qty > 0)
    .sort((left, right) => {
      return left.commodity_sku.localeCompare(right.commodity_sku) || left.id - right.id
    }),
)

const filteredItems = computed(() => {
  const keyword = skuFilter.value.trim().toLowerCase()
  let list = procurementItems.value

  if (keyword) {
    list = list.filter((item) => item.commodity_sku.toLowerCase().includes(keyword))
  }

  return list
})

const allSelectableIds = computed(() => filteredItems.value.map((item) => item.id))

const pagedItems = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredItems.value.slice(start, start + pageSize.value)
})

const {
  selectedIds,
  selectedCount,
  isAllSelected,
  isIndeterminate,
  toggleSelectAll,
  toggleRow,
  isRowSelected,
} = useCrossPageSelection({
  allSelectableIds,
  resetKey: () => props.suggestion?.id,
})

const exportButtonLabel = computed(() => `导出采购单 Excel（${selectedCount.value}项）`)

function draftValue<T extends keyof SuggestionItemPatch>(
  itemId: number,
  field: T,
  fallback: NonNullable<SuggestionItemPatch[T]>,
): SuggestionItemPatch[T] {
  return draftPatches.value[itemId]?.[field] ?? fallback
}

function updateDraft<T extends keyof SuggestionItemPatch>(
  itemId: number,
  field: T,
  value: SuggestionItemPatch[T],
): void {
  draftPatches.value[itemId] = {
    ...(draftPatches.value[itemId] ?? {}),
    [field]: value,
  }
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

function isPurchaseAdjusted(item: SuggestionItem): boolean {
  const generated = item.calculation_inputs_snapshot?.purchase.final_purchase_qty
  return generated !== undefined && Number(generated) !== Number(item.purchase_qty)
}

function countryQtyText(values: Record<string, number> | undefined): string {
  const entries = Object.entries(values || {}).filter(([, qty]) => Number(qty) > 0)
  if (entries.length === 0) return '-'
  return entries
    .map(([country, qty]) => `${getCountryLabel(country)} ${formatNumber(qty)}`)
    .join('，')
}

const ProcurementCalculationPanel = defineComponent({
  name: 'ProcurementCalculationPanel',
  props: {
    item: { type: Object as PropType<SuggestionItem>, required: true },
    compact: { type: Boolean, default: false },
  },
  setup(panelProps) {
    return () => {
      const snapshot = panelProps.item.calculation_inputs_snapshot
      if (!snapshot) {
        return h('div', { class: ['calculation-panel', { 'calculation-panel--mobile': panelProps.compact }] }, [
          h('div', { class: 'calculation-empty' }, '历史建议缺少完整计算依据'),
        ])
      }
      const purchase = snapshot.purchase
      const detailRows = panelProps.compact
        ? [
            ['各国补货量合计', formatNumber(purchase.country_restock_qty_total)],
            ['国内仓库存合计', formatNumber(purchase.local_stock_total)],
            ['安全库存量', formatNumber(purchase.safety_stock_qty)],
            ['生成时 / 当前', `${formatNumber(purchase.final_purchase_qty)} / ${formatNumber(panelProps.item.purchase_qty)}`],
          ]
        : [
            ['各国补货量合计', formatNumber(purchase.country_restock_qty_total)],
            [
              '国内仓可用 / 占用 / 合计',
              `${formatNumber(purchase.local_stock_available)} / ${formatNumber(purchase.local_stock_reserved)} / ${formatNumber(purchase.local_stock_total)}`,
            ],
            ['全国家销量合计', formatNumber(purchase.daily_velocity_total)],
            ['安全库存天数 / 安全库存量', `${snapshot.safety_stock_days} 天 / ${formatNumber(purchase.safety_stock_qty)}`],
            ['原始采购量', formatNumber(purchase.raw_purchase_qty)],
            ['生成时采购量 / 当前采购量', `${formatNumber(purchase.final_purchase_qty)} / ${formatNumber(panelProps.item.purchase_qty)}`],
          ]

      return h('div', { class: ['calculation-panel', { 'calculation-panel--mobile': panelProps.compact }] }, [
        h('div', { class: 'calculation-panel__header' }, [
          h('span', { class: 'calculation-formula' }, '采购量 = max(0, 各国补货量合计 - 国内仓库存合计 + 安全库存量)'),
          isPurchaseAdjusted(panelProps.item)
            ? h('span', { class: 'calculation-adjusted' }, '当前已手工调整')
            : null,
        ]),
        h(
          'div',
          { class: 'calculation-grid' },
          detailRows.map(([label, value]) =>
            h('div', { class: 'calculation-grid__item' }, [
              h('span', label),
              h('strong', value),
            ]),
          ),
        ),
        h('div', { class: 'calculation-country-line' }, `各国补货量：${countryQtyText(purchase.country_restock_qty_by_country)}`),
      ])
    }
  },
})

async function saveDrafts(): Promise<void> {
  if (!props.suggestion) return

  const entries = Object.entries(draftPatches.value)
  for (const [itemId, patch] of entries) {
    if (Object.keys(patch).length === 0) continue
    await patchSuggestionItem(props.suggestion.id, Number(itemId), patch)
  }
  draftPatches.value = {}
}

async function handleExport(): Promise<void> {
  if (!props.suggestion || selectedIds.value.length === 0) return

  exporting.value = true
  try {
    try {
      await saveDrafts()
    } catch (error) {
      ElMessage.error(getActionErrorMessage(error, '保存暂存修改失败，导出未执行'))
      return
    }

    let snapshot
    try {
      snapshot = await createProcurementSnapshot(props.suggestion.id, selectedIds.value)
    } catch (error) {
      ElMessage.error(getActionErrorMessage(error, '修改已保存，导出失败，请再次点击“导出”'))
      emit('refresh')
      return
    }

    try {
      const { blob, filename } = await downloadSnapshotBlob(snapshot.id)
      triggerBlobDownload(blob, filename)
      ElMessage.success('采购单导出成功')
    } catch (error) {
      ElMessage.warning(getActionErrorMessage(error, '导出已生成，下载失败，请在历史记录重试下载'))
    }

    emit('refresh')
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped lang="scss">
.procurement-list {
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

.table-toolbar__filters {
  display: flex;
  gap: $space-4;
  align-items: center;
}

.table-toolbar__actions {
  display: flex;
  gap: $space-2;
  align-items: center;
}

.calculation-panel {
  margin: $space-3 $space-4;
  padding: $space-3;
  border: 1px solid $color-border-subtle;
  border-radius: $radius-md;
  background: $color-bg-subtle;
}

.calculation-panel__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: $space-2;
  margin-bottom: $space-3;
}

.calculation-formula {
  font-family: $font-family-mono;
  font-size: $font-size-sm;
  color: $color-text-primary;
}

.calculation-adjusted {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 $space-2;
  border-radius: $radius-sm;
  color: $color-warning;
  background: $color-warning-soft;
  font-size: $font-size-xs;
}

.calculation-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: $space-2;
}

.calculation-grid__item {
  min-width: 0;
  padding: $space-2;
  border-radius: $radius-sm;
  background: $color-bg-base;
}

.calculation-grid__item > span {
  display: block;
  margin-bottom: 2px;
  color: $color-text-secondary;
  font-size: $font-size-xs;
}

.calculation-grid__item > strong {
  font-family: $font-family-mono;
  font-weight: $font-weight-semibold;
  color: $color-text-primary;
}

.calculation-country-line,
.calculation-empty {
  margin-top: $space-3;
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

@media (max-width: 767px) {
  .table-toolbar,
  .table-toolbar__filters,
  .table-toolbar__actions {
    width: 100%;
    align-items: stretch;
  }

  .table-toolbar {
    flex-direction: column;
  }

  .table-toolbar__filters :deep(.el-input),
  .table-toolbar__actions :deep(.el-button) {
    width: 100% !important;
  }

  .mobile-suggestion-card {
    display: flex;
    flex-direction: column;
    gap: $space-3;
  }

  .mobile-suggestion-card__head {
    display: flex;
    gap: $space-3;
    align-items: center;
  }

  .mobile-suggestion-card__head :deep(.sku-card) {
    min-width: 0;
  }

  .mobile-suggestion-card__body {
    display: grid;
    grid-template-columns: 1fr;
    gap: $space-2;
  }

  .mobile-field {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: $space-3;
    padding: $space-2;
    border-radius: $radius-md;
    background: $color-bg-subtle;
  }

  .mobile-field > span {
    color: $color-text-secondary;
    font-size: $font-size-xs;
  }

  .calculation-panel {
    margin: 0;
  }

  .calculation-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
