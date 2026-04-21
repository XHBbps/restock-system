<template>
  <el-empty
    v-if="suggestion?.restock_item_count === 0"
    description="本期无补货需求"
    :image-size="80"
  />
  <div v-else class="restock-list">
    <div class="table-toolbar">
      <el-input v-model="skuFilter" placeholder="SKU 搜索" clearable style="width: 220px" />
      <el-button
        v-if="editable"
        type="primary"
        :disabled="selectedIds.length === 0"
        :loading="exporting"
        @click="handleExport"
      >
        导出补货单 Excel
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="filteredItems"
      empty-text="本期无补货需求"
      @selection-change="onSelectionChange"
    >
      <el-table-column v-if="editable" type="selection" width="48" />
      <el-table-column type="expand" width="48">
        <template #default="{ row }">
          <div class="breakdown-panel">
            <div
              v-for="country in countryRows(row)"
              :key="country.country"
              class="country-row"
            >
              <div class="country-title">
                <strong>{{ country.country }}</strong>
                <span>{{ country.qty }}</span>
              </div>
              <div class="warehouse-list">
                <span
                  v-for="warehouse in country.warehouses"
                  :key="warehouse.id"
                  class="warehouse-chip"
                >
                  {{ warehouse.id }}: {{ warehouse.qty }}
                </span>
                <span v-if="country.warehouses.length === 0" class="muted">未拆仓</span>
              </div>
            </div>
          </div>
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
  </div>
</template>

<script setup lang="ts">
import type { SuggestionDetail, SuggestionItem } from '@/api/suggestion'
import { createRestockSnapshot, downloadSnapshotBlob } from '@/api/snapshot'
import SkuCard from '@/components/SkuCard.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { triggerBlobDownload } from '@/utils/download'
import { ElMessage } from 'element-plus'
import { computed, ref } from 'vue'

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
const selectedIds = ref<number[]>([])
const exporting = ref(false)

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
        .filter(([, whQty]) => Number(whQty) > 0)
        .map(([id, whQty]) => ({ id, qty: Number(whQty) })),
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

function onSelectionChange(rows: SuggestionItem[]): void {
  selectedIds.value = rows.map((row) => row.id)
}

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

.country-chips,
.warehouse-list {
  display: flex;
  flex-wrap: wrap;
  gap: $space-2;
}

.breakdown-panel {
  display: flex;
  flex-direction: column;
  gap: $space-3;
  padding: $space-3 $space-6;
  background: $color-bg-subtle;
}

.country-row {
  display: flex;
  flex-direction: column;
  gap: $space-2;
}

.country-title {
  display: flex;
  align-items: center;
  gap: $space-3;
}

.warehouse-chip {
  padding: 2px 8px;
  border-radius: $radius-pill;
  background: $color-brand-primary-soft;
  color: $color-brand-primary;
  font-size: $font-size-xs;
}

.muted {
  color: $color-text-secondary;
}
</style>
