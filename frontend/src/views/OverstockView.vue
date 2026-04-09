<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <div>
          <div class="card-title">积压提示</div>
          <div class="card-meta">支持分页查看积压 SKU，并记录是否已人工处理。</div>
        </div>
        <div class="actions">
          <el-switch v-model="showProcessed" active-text="显示已处理" inactive-text="仅未处理" @change="reload" />
        </div>
      </div>
    </template>

    <el-table v-loading="loading" :data="pagedRows">
      <el-table-column label="SKU" min-width="280" show-overflow-tooltip>
        <template #default="{ row }">
          <strong>{{ row.commodity_sku }}</strong>
          <div class="meta">{{ row.commodity_name || '-' }}</div>
        </template>
      </el-table-column>
      <el-table-column label="国家" prop="country" width="100" show-overflow-tooltip />
      <el-table-column label="仓库" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.warehouse_name || row.warehouse_id }}
        </template>
      </el-table-column>
      <el-table-column label="当前库存" prop="current_stock" width="120" align="right" show-overflow-tooltip />
      <el-table-column label="最近销售日期" width="160" show-overflow-tooltip>
        <template #default="{ row }">
          {{ formatDate(row.last_sale_date) }}
        </template>
      </el-table-column>
      <el-table-column label="处理状态" width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <el-tag v-if="row.processed_at" type="success">已处理</el-tag>
          <el-tag v-else type="warning">待处理</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" align="center" show-overflow-tooltip>
        <template #default="{ row }">
          <el-button v-if="!row.processed_at" link type="primary" @click="markProcessed(row)">
            标记为已处理
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <TablePaginationBar
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="rows.length"
      :page-sizes="[10, 20, 50]"
    />
  </el-card>
</template>

<script setup lang="ts">
import { listOverstock, markOverstockProcessed, type Overstock } from '@/api/monitor'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

const rows = ref<Overstock[]>([])
const loading = ref(false)
const showProcessed = ref(false)
const page = ref(1)
const pageSize = ref(10)

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return rows.value.slice(start, start + pageSize.value)
})

async function reload(): Promise<void> {
  loading.value = true
  try {
    rows.value = await listOverstock({ show_processed: showProcessed.value })
  } finally {
    loading.value = false
  }
}

function formatDate(value: string | null): string {
  return value ? dayjs(value).format('YYYY-MM-DD') : '无销售记录'
}

async function markProcessed(row: Overstock): Promise<void> {
  let note: string | undefined
  try {
    const { value } = await ElMessageBox.prompt('备注（可选）', '标记为已处理', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      inputType: 'textarea',
    })
    note = value || undefined
  } catch {
    return
  }
  try {
    await markOverstockProcessed(row.id, note)
    ElMessage.success('已完成标记。')
    await reload()
  } catch {
    ElMessage.error('操作失败。')
  }
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

.card-meta,
.meta {
  color: $color-text-secondary;
}

.card-meta {
  margin-top: 4px;
  font-size: $font-size-sm;
}

.meta {
  font-size: $font-size-xs;
  margin-top: 2px;
}

@media (max-width: 900px) {
  .card-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
