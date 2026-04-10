<template>
  <PageSectionCard title="商品">
    <template #actions>
      <el-input
        v-model="filters.keyword"
        placeholder="搜索 SKU / 商品名"
        clearable
        style="width: 220px"
        @keyup.enter="reload"
        @clear="reload"
      />
      <el-select
        v-model="filters.enabled"
        placeholder="启用状态"
        clearable
        style="width: 130px"
        @change="reload"
      >
        <el-option label="已启用" :value="true" />
        <el-option label="已禁用" :value="false" />
      </el-select>
      <el-button :loading="initLoading" @click="initFromListings">从商品同步初始化</el-button>
    </template>

    <el-table v-loading="loading" :data="rows" row-key="commodity_sku">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="expand-wrapper">
            <el-table :data="row.listings" size="small" :show-header="true">
              <el-table-column label="站点" prop="marketplace_id" min-width="120" />
              <el-table-column label="卖家SKU" prop="seller_sku" min-width="160" show-overflow-tooltip />
              <el-table-column label="7天销量" prop="day7_sale_num" width="100" align="right" />
              <el-table-column label="14天销量" prop="day14_sale_num" width="100" align="right" />
              <el-table-column label="30天销量" prop="day30_sale_num" width="100" align="right" />
              <el-table-column label="在售状态" width="100" align="center">
                <template #default="{ row: listing }">
                  <el-tag
                    :type="listing.online_status === 'Active' ? 'success' : 'info'"
                    size="small"
                  >
                    {{ listing.online_status === 'Active' ? '在售' : '不在售' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="最后同步" width="140">
                <template #default="{ row: listing }">
                  <span class="muted mono">{{ formatTime(listing.last_sync_at) }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="SKU" min-width="280">
        <template #default="{ row }">
          <SkuCard :sku="row.commodity_sku" :name="row.commodity_name" :image="row.main_image" />
        </template>
      </el-table-column>

      <el-table-column label="启用" width="100" align="center">
        <template #default="{ row }">
          <el-switch
            v-model="row.enabled"
            @change="(v: string | number | boolean) => updateEnabled(row, normalizeSwitchValue(v))"
          />
        </template>
      </el-table-column>

      <el-table-column label="覆盖提前期（天）" width="200">
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

      <el-table-column label="站点数" prop="listing_count" width="100" align="right" />
      <el-table-column label="30天总销量" prop="total_day30_sales" width="120" align="right" />
    </el-table>

    <TablePaginationBar
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100, 200]"
      @current-change="reload"
      @size-change="reload"
    />
  </PageSectionCard>
</template>

<script setup lang="ts">
import { listSkuOverview, type SkuOverviewItem } from '@/api/data'
import { initSkuConfigs, patchSkuConfig } from '@/api/config'
import SkuCard from '@/components/SkuCard.vue'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { normalizeSwitchValue } from '@/utils/element'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref, watch } from 'vue'

const rows = ref<SkuOverviewItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const loading = ref(false)
const initLoading = ref(false)

const filters = reactive({
  keyword: '',
  enabled: undefined as boolean | undefined,
})

watch(
  () => [filters.keyword, filters.enabled],
  () => {
    page.value = 1
  },
)

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listSkuOverview({
      keyword: filters.keyword || undefined,
      enabled: filters.enabled,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = resp.items
    total.value = resp.total
  } finally {
    loading.value = false
  }
}

async function updateEnabled(row: SkuOverviewItem, value: boolean): Promise<void> {
  try {
    await patchSkuConfig(row.commodity_sku, { enabled: value })
    ElMessage.success(`已${value ? '启用' : '禁用'} ${row.commodity_sku}`)
  } catch {
    row.enabled = !value
    ElMessage.error('更新失败。')
  }
}

async function updateLeadTime(row: SkuOverviewItem, value: number | undefined): Promise<void> {
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

function formatTime(value: string | null): string {
  if (!value) return '-'
  return dayjs(value).format('MM-DD HH:mm')
}

onMounted(reload)
</script>

<style lang="scss" scoped>
.expand-wrapper {
  padding: $space-3 $space-4;
}

.muted {
  color: $color-text-secondary;
}

.mono {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
}
</style>
