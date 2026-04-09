<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <span class="card-title">SKU 配置</span>
        <div class="card-actions">
          <el-input
            v-model="keyword"
            placeholder="搜索 SKU"
            clearable
            style="width: 240px"
            @keyup.enter="reload"
            @clear="reload"
          />
          <el-button :loading="initLoading" @click="initFromListings">从商品同步初始化</el-button>
        </div>
      </div>
    </template>

    <el-table v-loading="loading" :data="rows">
      <el-table-column label="SKU" min-width="280" show-overflow-tooltip>
        <template #default="{ row }">
          <SkuCard :sku="row.commodity_sku" :name="row.commodity_name" :image="row.main_image" />
        </template>
      </el-table-column>
      <el-table-column label="启用" width="100" align="center" show-overflow-tooltip>
        <template #default="{ row }">
          <el-switch v-model="row.enabled" @change="(v) => updateEnabled(row, normalizeSwitchValue(v))" />
        </template>
      </el-table-column>
      <el-table-column label="覆盖提前期（天）" width="200" show-overflow-tooltip>
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
import { initSkuConfigs, listSkuConfigs, patchSkuConfig, type SkuConfig } from '@/api/config'
import SkuCard from '@/components/SkuCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { normalizeSwitchValue } from '@/utils/element'
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

const rows = ref<SkuConfig[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const keyword = ref('')
const loading = ref(false)
const initLoading = ref(false)

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listSkuConfigs({
      keyword: keyword.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = resp.items
    total.value = resp.total
  } finally {
    loading.value = false
  }
}

async function updateEnabled(row: SkuConfig, value: boolean): Promise<void> {
  try {
    await patchSkuConfig(row.commodity_sku, { enabled: value })
    ElMessage.success(`已${value ? '启用' : '禁用'} ${row.commodity_sku}`)
  } catch {
    row.enabled = !value
    ElMessage.error('更新失败。')
  }
}

async function updateLeadTime(row: SkuConfig, value: number | undefined): Promise<void> {
  try {
    await patchSkuConfig(row.commodity_sku, { lead_time_days: value ?? null })
    ElMessage.success(`已更新 ${row.commodity_sku} 的提前期配置。`)
  } catch {
    ElMessage.error('更新失败。')
  }
}

async function initFromListings(): Promise<void> {
  initLoading.value = true
  try {
    const resp = await initSkuConfigs()
    await reload()
    ElMessage.success(`已初始化 ${resp.created} 个 SKU，当前共 ${resp.total} 个配置。`)
  } catch {
    ElMessage.error('初始化 SKU 配置失败。')
  } finally {
    initLoading.value = false
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

.card-actions {
  display: flex;
  align-items: center;
  gap: $space-3;
}

.card-title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}

@media (max-width: 900px) {
  .card-header,
  .card-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
