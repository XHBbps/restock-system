<template>
  <PageSectionCard title="历史记录">
    <template #actions>
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        style="width: 280px"
        @change="reload"
      />
      <el-select v-model="status" placeholder="状态" clearable style="width: 140px" @change="reload">
        <el-option label="草稿" value="draft" />
        <el-option label="部分推送" value="partial" />
        <el-option label="已推送" value="pushed" />
        <el-option label="已归档" value="archived" />
        <el-option label="异常" value="error" />
      </el-select>
      <el-input
        v-model="sku"
        placeholder="SKU 关键字"
        clearable
        style="width: 200px"
        @clear="reload"
        @keyup.enter="reload"
      />
    </template>

    <el-table v-loading="loading" :data="pagedRows" @sort-change="handleSortChange">
      <el-table-column label="建议单 ID" prop="id" width="130" sortable="custom" show-overflow-tooltip />
      <el-table-column label="生成时间" prop="created_at" min-width="180" sortable="custom" show-overflow-tooltip>
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="触发方式" prop="triggered_by" width="140" sortable="custom" show-overflow-tooltip />
      <el-table-column label="状态" prop="status" width="120" sortable="custom">
        <template #default="{ row }">
          <el-tag :type="getSuggestionStatusMeta(row.status).tagType">
            {{ getSuggestionStatusMeta(row.status).label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="条目数" prop="total_items" width="100" align="right" sortable="custom" show-overflow-tooltip />
      <el-table-column label="已推送" prop="pushed_items" width="100" align="right" sortable="custom" show-overflow-tooltip />
      <el-table-column label="失败数" prop="failed_items" width="100" align="right" sortable="custom" show-overflow-tooltip />
      <el-table-column label="推送成功率" prop="success_rate" width="120" align="right" sortable="custom">
        <template #default="{ row }">
          {{ successRate(row) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center">
        <template #default="{ row }">
          <el-button link type="primary" @click="goDetail(row.id)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <TablePaginationBar
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="rows.length"
      :page-sizes="[20, 50, 100]"
    />
  </PageSectionCard>
</template>

<script setup lang="ts">
import { listSuggestions, type Suggestion } from '@/api/suggestion'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { getSuggestionStatusMeta } from '@/utils/status'
import { formatDateTime } from '@/utils/format'
import { normalizeSortOrder, type SortChangeEvent, type SortState } from '@/utils/tableSort'
import { getActionErrorMessage } from '@/utils/apiError'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const rows = ref<Suggestion[]>([])
const page = ref(1)
const pageSize = ref(20)
const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return rows.value.slice(start, start + pageSize.value)
})
const loading = ref(false)
const sortState = ref<SortState>({ prop: 'created_at', order: 'desc' })

const dateRange = ref<[string, string] | null>(null)
const status = ref<string | undefined>(undefined)
const sku = ref('')

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listSuggestions({
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      status: status.value,
      sku: sku.value || undefined,
      page: 1,
      page_size: 5000,
      sort_by: sortState.value.prop,
      sort_order: sortState.value.order,
    })
    rows.value = resp.items
    page.value = 1
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载失败'))
  } finally {
    loading.value = false
  }
}

function successRate(row: Suggestion): string {
  if (!row.total_items) return '-'
  const rate = (row.pushed_items / row.total_items) * 100
  return `${rate.toFixed(0)}%`
}

function goDetail(id: number): void {
  router.push(`/restock/suggestions/${id}`)
}

function handleSortChange({ prop, order }: SortChangeEvent): void {
  const normalizedOrder = normalizeSortOrder(order)
  sortState.value = normalizedOrder && prop
    ? { prop, order: normalizedOrder }
    : { prop: 'created_at', order: 'desc' }
  page.value = 1
  void reload()
}

onMounted(reload)
</script>

<style lang="scss" scoped>
</style>
