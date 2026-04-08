<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <span class="card-title">历史建议单</span>
        <div class="filters">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="—"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 280px"
            @change="reload"
          />
          <el-select
            v-model="status"
            placeholder="状态"
            clearable
            style="width: 140px"
            @change="reload"
          >
            <el-option label="草稿" value="draft" />
            <el-option label="部分推送" value="partial" />
            <el-option label="已推送" value="pushed" />
            <el-option label="已归档" value="archived" />
            <el-option label="错误" value="error" />
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

    <el-table :data="rows" v-loading="loading">
      <el-table-column label="ID" prop="id" width="80" />
      <el-table-column label="生成时间" width="180">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="触发方式" prop="triggered_by" width="120" />
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="条目数" prop="total_items" width="100" align="right" />
      <el-table-column label="已推送" prop="pushed_items" width="100" align="right" />
      <el-table-column label="失败" prop="failed_items" width="100" align="right" />
      <el-table-column label="推送成功率" width="120" align="right">
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

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100]"
      layout="total, sizes, prev, pager, next"
      style="margin-top: 16px; justify-content: flex-end"
      @current-change="reload"
      @size-change="reload"
    />
  </el-card>
</template>

<script setup lang="ts">
import { listSuggestions, type Suggestion } from '@/api/suggestion'
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
      page_size: pageSize.value
    })
    rows.value = resp.items
    total.value = resp.total
  } finally {
    loading.value = false
  }
}

function formatTime(t: string): string {
  return dayjs(t).format('YYYY-MM-DD HH:mm')
}

function statusType(s: string): string {
  return (
    {
      draft: 'warning',
      partial: 'warning',
      pushed: 'success',
      archived: 'info',
      error: 'danger'
    } as Record<string, string>
  )[s] || 'info'
}

function statusLabel(s: string): string {
  return (
    {
      draft: '草稿',
      partial: '部分推送',
      pushed: '已推送',
      archived: '已归档',
      error: '错误'
    } as Record<string, string>
  )[s] || s
}

function successRate(row: Suggestion): string {
  if (!row.total_items) return '-'
  const r = (row.pushed_items / row.total_items) * 100
  return `${r.toFixed(0)}%`
}

function goDetail(id: number): void {
  router.push(`/suggestions/${id}`)
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
.filters {
  display: flex;
  gap: $space-3;
}
</style>
