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
        <label class="urgent-only-switch">
          <el-switch v-model="urgentOnly" />
          <span>仅显示紧急 (≤30 天)</span>
        </label>
      </div>
      <div class="table-toolbar__actions">
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
    </div>

    <el-table
      v-loading="loading"
      :data="pagedItems"
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
      <el-table-column label="采购日期" prop="purchase_date" width="240">
        <template #default="{ row }">
          <PurchaseDateCell
            :editable="editable"
            :date="draftValue(row.id, 'purchase_date', row.purchase_date)"
            @update:date="(value: string | null) => updateDraft(row.id, 'purchase_date', value)"
          />
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
import PurchaseDateCell from '@/components/PurchaseDateCell.vue'
import SkuCard from '@/components/SkuCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { triggerBlobDownload } from '@/utils/download'
import { ElMessage } from 'element-plus'
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  suggestion: SuggestionDetail | null
  items: SuggestionItem[]
  loading?: boolean
}>()

const emit = defineEmits<{
  refresh: []
}>()

const skuFilter = ref('')
const urgentOnly = ref(false)
const page = ref(1)
const pageSize = ref(20)
const selectedIds = ref<number[]>([])
const exporting = ref(false)
const draftPatches = ref<Record<number, SuggestionItemPatch>>({})

// 过滤条件变化时回到第一页
watch([skuFilter, urgentOnly], () => {
  page.value = 1
})

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
  let list = procurementItems.value
  if (keyword) {
    list = list.filter((item) => item.commodity_sku.toLowerCase().includes(keyword))
  }
  if (urgentOnly.value) {
    // 仅紧急：purchase_date 在今天 + 30 天之内（含过期的，排除 > 30 天的宽松/不紧急）
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const threshold = new Date(today)
    threshold.setDate(threshold.getDate() + 30)
    list = list.filter((item) => {
      if (!item.purchase_date) return false
      const pd = new Date(item.purchase_date)
      pd.setHours(0, 0, 0, 0)
      return pd <= threshold
    })
  }
  return list
})

const pagedItems = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredItems.value.slice(start, start + pageSize.value)
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
  // 分阶段处理：保存失败 → 中止导出；导出失败 → 提示已保存可再次导出；下载失败 → 导出成功但下载失败
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
      ElMessage.error(getActionErrorMessage(error, '修改已保存，导出失败，请再次点击"导出"'))
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

.urgent-only-switch {
  display: inline-flex;
  gap: $space-2;
  align-items: center;
  font-size: $font-size-sm;
  color: $color-text-secondary;
  cursor: pointer;
}

.table-toolbar__actions {
  display: flex;
  gap: $space-2;
  align-items: center;
}
</style>
