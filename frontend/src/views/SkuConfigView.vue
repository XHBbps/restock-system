<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <span class="card-title">SKU 配置</span>
        <el-input
          v-model="keyword"
          placeholder="搜索 SKU"
          clearable
          style="width: 240px"
          @keyup.enter="reload"
          @clear="reload"
        />
      </div>
    </template>

    <el-table :data="rows" v-loading="loading">
      <el-table-column label="SKU" min-width="280">
        <template #default="{ row }">
          <SkuCard :sku="row.commodity_sku" :name="row.commodity_name" :image="row.main_image" />
        </template>
      </el-table-column>
      <el-table-column label="启用" width="100" align="center">
        <template #default="{ row }">
          <el-switch v-model="row.enabled" @change="(v: boolean) => updateEnabled(row, v)" />
        </template>
      </el-table-column>
      <el-table-column label="覆盖提前期(天)" width="200">
        <template #default="{ row }">
          <el-input-number
            v-model="row.lead_time_days"
            :min="0"
            :max="365"
            :controls="false"
            placeholder="使用全局"
            size="small"
            @change="(v: number | undefined) => updateLeadTime(row, v)"
          />
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
import { listSkuConfigs, patchSkuConfig, type SkuConfig } from '@/api/config'
import SkuCard from '@/components/SkuCard.vue'
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

const rows = ref<SkuConfig[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const keyword = ref('')
const loading = ref(false)

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listSkuConfigs({
      keyword: keyword.value || undefined,
      page: page.value,
      page_size: pageSize.value
    })
    rows.value = resp.items
    total.value = resp.total
  } finally {
    loading.value = false
  }
}

async function updateEnabled(row: SkuConfig, v: boolean): Promise<void> {
  try {
    await patchSkuConfig(row.commodity_sku, { enabled: v })
    ElMessage.success(`已${v ? '启用' : '禁用'} ${row.commodity_sku}`)
  } catch {
    row.enabled = !v
    ElMessage.error('更新失败')
  }
}

async function updateLeadTime(row: SkuConfig, v: number | undefined): Promise<void> {
  try {
    await patchSkuConfig(row.commodity_sku, { lead_time_days: v ?? null })
  } catch {
    ElMessage.error('更新失败')
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
</style>
