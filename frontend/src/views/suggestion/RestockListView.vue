<template>
  <el-empty
    v-if="suggestion?.restock_item_count === 0"
    description="本期无补货需求"
    :image-size="80"
  />
  <div v-else class="restock-list">
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
      empty-text="本期无补货需求"
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
                v-for="country in countryRows(row)"
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
                    未拆仓（{{ country.qty }} 件待分配）
                  </el-tag>
                </td>
              </tr>
            </tbody>
          </table>
        </template>
      </el-table-column>
      <el-table-column label="商品信息" min-width="260">
        <template #default="{ row }">
          <SkuCard :sku="row.commodity_sku" :name="row.commodity_name" :image="row.main_image" />
        </template>
      </el-table-column>
      <el-table-column label="补货量" width="120" align="right">
        <template #default="{ row }">{{ restockTotal(row) }}</template>
      </el-table-column>
      <el-table-column label="国家分布" min-width="220">
        <template #default="{ row }">
          <div class="country-chips">
            <el-tag
              v-for="country in countryRows(row)"
              :key="country.country"
              size="small"
            >
              {{ country.country }}: {{ country.qty }}
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.restock_export_status === 'exported' ? 'success' : 'warning'" size="small">
            {{ row.restock_export_status === 'exported' ? '已导出' : '未导出' }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>

    <MobileRecordList
      v-else
      :items="pagedItems"
      :loading="loading"
      row-key="id"
      empty-text="本期无补货需求"
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
          <div class="mobile-suggestion-card__stats">
            <div class="mobile-field">
              <span>补货量</span>
              <strong>{{ restockTotal(row) }}</strong>
            </div>
            <div class="mobile-field">
              <span>状态</span>
              <el-tag :type="row.restock_export_status === 'exported' ? 'success' : 'warning'" size="small">
                {{ row.restock_export_status === 'exported' ? '已导出' : '未导出' }}
              </el-tag>
            </div>
          </div>
          <div class="country-chips">
            <el-tag v-for="country in countryRows(row)" :key="country.country" size="small">
              {{ country.country }}: {{ country.qty }}
            </el-tag>
          </div>
          <el-collapse v-if="countryRows(row).length > 0" class="mobile-detail-collapse">
            <el-collapse-item title="仓库分配" name="breakdown">
              <table class="breakdown-table mobile-breakdown-table">
                <tbody>
                  <tr v-for="country in countryRows(row)" :key="country.country" class="breakdown-row">
                    <td class="breakdown-col-country">{{ getCountryLabel(country.country) }}</td>
                    <td class="breakdown-col-qty">{{ country.qty }}</td>
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
                        未拆仓（{{ country.qty }}）
                      </el-tag>
                    </td>
                  </tr>
                </tbody>
              </table>
            </el-collapse-item>
          </el-collapse>
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
import { listWarehouses, type Warehouse } from '@/api/config'
import type { SuggestionDetail, SuggestionItem } from '@/api/suggestion'
import { createRestockSnapshot, downloadSnapshotBlob } from '@/api/snapshot'
import MobileRecordList from '@/components/MobileRecordList.vue'
import SkuCard from '@/components/SkuCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { useResponsive } from '@/composables/useResponsive'
import { getActionErrorMessage } from '@/utils/apiError'
import { getCountryLabel } from '@/utils/countries'
import { triggerBlobDownload } from '@/utils/download'
import { useCrossPageSelection } from '@/views/suggestion/useCrossPageSelection'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'

interface CountryRow {
  country: string
  qty: number
  warehouses: { id: string; qty: number }[]
}

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
const warehouseMap = ref<Record<string, string>>({})

watch(skuFilter, () => {
  page.value = 1
})

function warehouseLabel(warehouseId: string): string {
  const name = warehouseMap.value[warehouseId]
  return name ? `${name} (${warehouseId})` : warehouseId
}

onMounted(async () => {
  try {
    const warehouses = await listWarehouses()
    const map: Record<string, string> = {}
    for (const warehouse of warehouses as Warehouse[]) {
      map[warehouse.id] = warehouse.name
    }
    warehouseMap.value = map
  } catch {
    warehouseMap.value = {}
  }
})

const editable = computed(() => props.suggestion?.status === 'draft')

function restockTotal(item: SuggestionItem): number {
  return Object.values(item.country_breakdown || {}).reduce((sum, qty) => sum + Number(qty || 0), 0)
}

function countryRows(item: SuggestionItem): CountryRow[] {
  return Object.entries(item.country_breakdown || {})
    .filter(([, qty]) => Number(qty) > 0)
    .map(([country, qty]) => ({
      country,
      qty: Number(qty),
      warehouses: Object.entries(item.warehouse_breakdown?.[country] || {})
        .filter(([, warehouseQty]) => Number(warehouseQty) > 0)
        .map(([id, warehouseQty]) => ({ id, qty: Number(warehouseQty) })),
    }))
}

const restockItems = computed(() =>
  props.items
    .filter((item) => restockTotal(item) > 0)
    .sort((left, right) => left.commodity_sku.localeCompare(right.commodity_sku)),
)

const filteredItems = computed(() => {
  const keyword = skuFilter.value.trim().toLowerCase()
  if (!keyword) return restockItems.value
  return restockItems.value.filter((item) => item.commodity_sku.toLowerCase().includes(keyword))
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

const exportButtonLabel = computed(() => `导出补货单 Excel (${selectedCount.value}项)`)

async function handleExport(): Promise<void> {
  if (!props.suggestion || selectedIds.value.length === 0) return

  exporting.value = true
  let snapshotId: number | null = null

  try {
    const snapshot = await createRestockSnapshot(props.suggestion.id, selectedIds.value)
    snapshotId = snapshot.id
    const { blob, filename } = await downloadSnapshotBlob(snapshot.id)
    triggerBlobDownload(blob, filename)
    ElMessage.success('补货单导出成功')
    emit('refresh')
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, snapshotId ? '导出成功但下载失败' : '补货导出失败'))
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped lang="scss">
.restock-list {
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

.country-chips {
  display: flex;
  flex-wrap: wrap;
  gap: $space-2;
}

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
    align-items: center;
    gap: $space-3;
  }

  .mobile-suggestion-card__head :deep(.sku-card) {
    min-width: 0;
  }

  .mobile-suggestion-card__stats {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: $space-2;
  }

  .mobile-field {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    padding: $space-2;
    border-radius: $radius-md;
    background: $color-bg-subtle;
  }

  .mobile-field > span {
    color: $color-text-secondary;
    font-size: $font-size-xs;
  }

  .mobile-field > strong {
    font-weight: $font-weight-semibold;
  }

  .mobile-detail-collapse {
    border: 0;
  }

  .mobile-detail-collapse :deep(.el-collapse-item__header),
  .mobile-detail-collapse :deep(.el-collapse-item__wrap) {
    border: 0;
  }

  .mobile-detail-collapse :deep(.el-collapse-item__header) {
    height: 36px;
    font-size: $font-size-xs;
  }

  .mobile-detail-collapse :deep(.el-collapse-item__content) {
    padding: 0;
  }

  .mobile-breakdown-table {
    display: block;
    width: 100%;
    margin: 0;
    overflow-x: auto;
  }

  .breakdown-col-country {
    width: 96px;
  }

  .breakdown-col-warehouses {
    min-width: 220px;
  }
}
</style>
