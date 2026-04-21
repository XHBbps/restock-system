<template>
  <el-empty
    v-if="suggestion?.procurement_item_count === 0"
    description="本期无采购需求"
    :image-size="80"
  />
  <div v-else class="procurement-list">
    <div class="table-toolbar">
      <el-input v-model="skuFilter" placeholder="SKU 搜索" clearable style="width: 220px" />
      <el-button
        v-if="editable"
        type="primary"
        :disabled="selectedIds.length === 0"
        :loading="exporting"
        @click="handleExport"
      >
        导出采购单 Excel
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="filteredItems"
      empty-text="本期无采购需求"
      @selection-change="onSelectionChange"
    >
      <el-table-column v-if="editable" type="selection" width="48" />
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
            @update:model-value="(value: number | undefined) => updateDraft(row.id, 'purchase_qty', Number(value ?? 0))"
          />
          <span v-else>{{ row.purchase_qty }}</span>
        </template>
      </el-table-column>
      <el-table-column label="采购日期" prop="purchase_date" width="180">
        <template #default="{ row }">
          <el-date-picker
            v-if="editable"
            :model-value="draftValue(row.id, 'purchase_date', row.purchase_date)"
            type="date"
            value-format="YYYY-MM-DD"
            size="small"
            @update:model-value="(value: string | null) => updateDraft(row.id, 'purchase_date', value)"
          />
          <PurchaseDateCell v-else :date="row.purchase_date" />
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
import PurchaseDateCell from '@/components/PurchaseDateCell.vue'
import SkuCard from '@/components/SkuCard.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { triggerBlobDownload } from '@/utils/download'
import { ElMessage } from 'element-plus'
import { computed, ref } from 'vue'

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
const draftPatches = ref<Record<number, SuggestionItemPatch>>({})

const editable = computed(() => props.suggestion?.status === 'draft')

const procurementItems = computed(() =>
  props.items
    .filter((item) => item.purchase_qty > 0)
    .sort((left, right) => {
      const leftDate = left.purchase_date || '9999-12-31'
      const rightDate = right.purchase_date || '9999-12-31'
      return leftDate.localeCompare(rightDate) || left.commodity_sku.localeCompare(right.commodity_sku)
    }),
)

const filteredItems = computed(() => {
  const keyword = skuFilter.value.trim().toLowerCase()
  if (!keyword) return procurementItems.value
  return procurementItems.value.filter((item) => item.commodity_sku.toLowerCase().includes(keyword))
})

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

function onSelectionChange(rows: SuggestionItem[]): void {
  selectedIds.value = rows.map((row) => row.id)
}

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
  let snapshotId: number | null = null
  try {
    await saveDrafts()
    const snapshot = await createProcurementSnapshot(props.suggestion.id, selectedIds.value)
    snapshotId = snapshot.id
    const { blob, filename } = await downloadSnapshotBlob(snapshot.id)
    triggerBlobDownload(blob, filename)
    ElMessage.success('采购单导出成功')
    emit('refresh')
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, snapshotId ? '导出成功但下载失败' : '采购导出失败'))
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
</style>
