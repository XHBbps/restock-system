<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <div>
          <div class="card-title">历史记录</div>
          <div class="card-meta">按时间、状态和 SKU 过滤历史建议单。</div>
        </div>
        <div class="filters">
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
        </div>
      </div>
    </template>

    <el-table v-loading="loading" :data="rows">
      <el-table-column label="建议单 ID" prop="id" width="100" sortable show-overflow-tooltip />
      <el-table-column label="生成时间" width="180" sortable show-overflow-tooltip>
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="触发方式" prop="triggered_by" width="140" sortable show-overflow-tooltip />
      <el-table-column label="状态" width="120" sortable show-overflow-tooltip>
        <template #default="{ row }">
          <el-tag :type="getSuggestionStatusMeta(row.status).tagType">
            {{ getSuggestionStatusMeta(row.status).label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="条目数" prop="total_items" width="100" align="right" sortable show-overflow-tooltip />
      <el-table-column label="已推送" prop="pushed_items" width="100" align="right" sortable show-overflow-tooltip />
      <el-table-column label="失败数" prop="failed_items" width="100" align="right" sortable show-overflow-tooltip />
      <el-table-column label="推送成功率" width="120" align="right" sortable show-overflow-tooltip>
        <template #default="{ row }">
          {{ successRate(row) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center" show-overflow-tooltip>
        <template #default="{ row }">
          <el-button link type="primary" @click="goDetail(row.id)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <TablePaginationBar
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100]"
      @current-change="reload"
      @size-change="reload"
    />
  </el-card>
</template>

<script setup lang="ts">
import { listSuggestions, type Suggestion } from '@/api/suggestion'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { getSuggestionStatusMeta } from '@/utils/status'
import dayjs from 'dayjs'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const rows = ref<Suggestion[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

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
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = resp.items
    total.value = resp.total
  } finally {
    loading.value = false
  }
}

function formatTime(value: string): string {
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

function successRate(row: Suggestion): string {
  if (!row.total_items) return '-'
  const rate = (row.pushed_items / row.total_items) * 100
  return `${rate.toFixed(0)}%`
}

function goDetail(id: number): void {
  router.push(`/replenishment/suggestions/${id}`)
}

onMounted(reload)
</script>

<style lang="scss" scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-4;
}

.card-title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}

.card-meta {
  margin-top: 4px;
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.filters {
  display: flex;
  gap: $space-3;
  flex-wrap: wrap;
}

@media (max-width: 900px) {
  .card-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
