<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <span class="card-title">积压 SKU 提示</span>
        <div class="actions">
          <el-switch
            v-model="showProcessed"
            active-text="显示已处理"
            inactive-text="仅显示未处理"
            @change="reload"
          />
        </div>
      </div>
    </template>

    <el-table :data="rows" v-loading="loading">
      <el-table-column label="SKU" min-width="280">
        <template #default="{ row }">
          <strong>{{ row.commodity_sku }}</strong>
          <div class="meta">{{ row.commodity_name || '-' }}</div>
        </template>
      </el-table-column>
      <el-table-column label="国家" prop="country" width="100" />
      <el-table-column label="仓库" min-width="180">
        <template #default="{ row }">
          {{ row.warehouse_name || row.warehouse_id }}
        </template>
      </el-table-column>
      <el-table-column label="当前库存" prop="current_stock" width="120" align="right" />
      <el-table-column label="最后销售日期" width="160">
        <template #default="{ row }">
          {{ formatDate(row.last_sale_date) }}
        </template>
      </el-table-column>
      <el-table-column label="处理状态" width="160">
        <template #default="{ row }">
          <el-tag v-if="row.processed_at" type="success">已处理</el-tag>
          <el-tag v-else type="warning">待处理</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" align="center">
        <template #default="{ row }">
          <el-button
            v-if="!row.processed_at"
            link
            type="primary"
            @click="markProcessed(row)"
          >
            标为已处理
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { listOverstock, markOverstockProcessed, type Overstock } from '@/api/monitor'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'

const rows = ref<Overstock[]>([])
const loading = ref(false)
const showProcessed = ref(false)

async function reload(): Promise<void> {
  loading.value = true
  try {
    rows.value = await listOverstock({ show_processed: showProcessed.value })
  } finally {
    loading.value = false
  }
}

function formatDate(d: string | null): string {
  return d ? dayjs(d).format('YYYY-MM-DD') : '无销售记录'
}

async function markProcessed(row: Overstock): Promise<void> {
  let note: string | undefined
  try {
    const { value } = await ElMessageBox.prompt('备注（可选）', '标为已处理', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      inputType: 'textarea'
    })
    note = value || undefined
  } catch {
    return
  }
  try {
    await markOverstockProcessed(row.id, note)
    ElMessage.success('已标记')
    await reload()
  } catch {
    ElMessage.error('操作失败')
  }
}

onMounted(reload)
</script>

<style lang="scss" scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}
.meta {
  color: $color-text-secondary;
  font-size: $font-size-xs;
  margin-top: 2px;
}
</style>
