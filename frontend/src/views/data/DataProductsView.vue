<template>
  <PageSectionCard title="商品主数据">
    <template #actions>
      <el-input
        v-model="filters.keyword"
        placeholder="搜索 SKU / 商品名"
        clearable
        style="width: 220px"
        @keyup.enter="reloadFirstPage"
        @clear="reloadFirstPage"
      />
      <el-select
        v-model="filters.enabled"
        placeholder="启用状态"
        clearable
        style="width: 130px"
        @change="reloadFirstPage"
      >
        <el-option label="已启用" :value="true" />
        <el-option label="已禁用" :value="false" />
      </el-select>
      <el-button
        :loading="initLoading"
        :disabled="!auth.hasPermission('data_base:edit')"
        @click="initFromListings"
      >
        同步商品主数据
      </el-button>
    </template>

    <el-table v-if="!isMobile" v-loading="loading" :data="rows" row-key="commodity_sku">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="expand-wrapper">
            <el-table :data="row.listings" size="small" :show-header="true">
              <el-table-column label="站点" prop="marketplace_id" min-width="120" />
              <el-table-column label="卖家 SKU" prop="seller_sku" min-width="160" show-overflow-tooltip />
              <el-table-column label="7天销量" prop="day7_sale_num" width="100" align="right" />
              <el-table-column label="14天销量" prop="day14_sale_num" width="100" align="right" />
              <el-table-column label="30天销量" prop="day30_sale_num" width="100" align="right" />
              <el-table-column label="在售状态" width="100" align="center">
                <template #default="{ row: listing }">
                  <el-tag :type="getListingOnlineStatusMeta(listing.online_status).tagType" size="small">
                    {{ getListingOnlineStatusMeta(listing.online_status).label }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="同步时间" width="168">
                <template #default="{ row: listing }">
                  <span class="muted mono">{{ formatUpdateTime(listing.last_sync_at) }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="商品信息" min-width="300">
        <template #default="{ row }">
          <SkuCard :sku="row.commodity_sku" :name="row.commodity_name" :image="row.main_image" />
        </template>
      </el-table-column>

      <el-table-column label="启用" width="100" align="center">
        <template #default="{ row }">
          <el-switch
            v-model="row.enabled"
            :disabled="!auth.hasPermission('data_base:edit')"
            @change="(v: string | number | boolean) => updateEnabled(row, normalizeSwitchValue(v))"
          />
        </template>
      </el-table-column>

      <el-table-column label="listing数" prop="listing_count" width="100" align="right" />
      <el-table-column label="30天总销量" prop="total_day30_sales" width="120" align="right" />
    </el-table>

    <MobileRecordList
      v-else
      :items="rows"
      :loading="loading"
      row-key="commodity_sku"
      empty-text="暂无商品"
    >
      <template #default="{ item: row }">
        <div class="mobile-product-card">
          <div class="mobile-product-card__main">
            <SkuCard :sku="row.commodity_sku" :name="row.commodity_name" :image="row.main_image" />
            <el-switch
              v-model="row.enabled"
              :disabled="!auth.hasPermission('data_base:edit')"
              @change="(v: string | number | boolean) => updateEnabled(row, normalizeSwitchValue(v))"
            />
          </div>
          <div class="mobile-kv-grid">
            <div>
              <span>状态</span>
              <strong>{{ row.enabled ? '已启用' : '已禁用' }}</strong>
            </div>
            <div>
              <span>listing 数</span>
              <strong>{{ row.listing_count }}</strong>
            </div>
            <div>
              <span>30 天销量</span>
              <strong>{{ row.total_day30_sales }}</strong>
            </div>
          </div>
          <el-collapse v-if="row.listings.length > 0" class="mobile-listing-collapse">
            <el-collapse-item :title="`listing 明细（${row.listings.length}）`" name="listings">
              <div class="mobile-listing-list">
                <div v-for="listing in row.listings" :key="listing.id" class="mobile-listing-item">
                  <div class="mobile-listing-item__head">
                    <strong>{{ listing.marketplace_id }}</strong>
                    <el-tag :type="getListingOnlineStatusMeta(listing.online_status).tagType" size="small">
                      {{ getListingOnlineStatusMeta(listing.online_status).label }}
                    </el-tag>
                  </div>
                  <div class="mobile-listing-item__sku">{{ listing.seller_sku || '-' }}</div>
                  <div class="mobile-listing-item__sales">
                    <span>7天 {{ listing.day7_sale_num ?? 0 }}</span>
                    <span>14天 {{ listing.day14_sale_num ?? 0 }}</span>
                    <span>30天 {{ listing.day30_sale_num ?? 0 }}</span>
                  </div>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </template>
    </MobileRecordList>

    <TablePaginationBar
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100, 200]"
      @current-change="handlePageChange"
      @size-change="handlePageSizeChange"
    />
  </PageSectionCard>
</template>

<script setup lang="ts">
import { listSkuOverview, type SkuOverviewItem } from '@/api/data'
import { initSkuConfigs, patchSkuConfig } from '@/api/config'
import MobileRecordList from '@/components/MobileRecordList.vue'
import SkuCard from '@/components/SkuCard.vue'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { useResponsive } from '@/composables/useResponsive'
import { normalizeSwitchValue } from '@/utils/element'
import { formatUpdateTime } from '@/utils/format'
import { getListingOnlineStatusMeta } from '@/utils/status'
import { getActionErrorMessage } from '@/utils/apiError'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

const auth = useAuthStore()
const { isMobile } = useResponsive()
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

async function reload(resetPage = false): Promise<void> {
  if (resetPage) {
    page.value = 1
  }
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
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载失败'))
  } finally {
    loading.value = false
  }
}

async function updateEnabled(row: SkuOverviewItem, value: boolean): Promise<void> {
  try {
    await patchSkuConfig(row.commodity_sku, { enabled: value })
    await reload(false)
    ElMessage.success(`已${value ? '启用' : '禁用'} ${row.commodity_sku}`)
  } catch (err) {
    row.enabled = !value
    ElMessage.error(getActionErrorMessage(err, '更新失败'))
  }
}

async function initFromListings(): Promise<void> {
  initLoading.value = true
  try {
    const resp = await initSkuConfigs()
    await reload(true)
    ElMessage.success(`已补齐 ${resp.created} 条 SKU 配置，当前共 ${resp.total} 条`)
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '同步商品主数据失败'))
  } finally {
    initLoading.value = false
  }
}

onMounted(reload)

function reloadFirstPage(): void {
  void reload(true)
}

function handlePageChange(value: number): void {
  page.value = value
  void reload(false)
}

function handlePageSizeChange(value: number): void {
  pageSize.value = value
  void reload(true)
}

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

@media (max-width: 767px) {
  .mobile-product-card {
    display: flex;
    flex-direction: column;
    gap: $space-3;
  }

  .mobile-product-card__main {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: $space-3;
  }

  .mobile-product-card__main :deep(.sku-card) {
    min-width: 0;
  }

  .mobile-kv-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: $space-2;
  }

  .mobile-kv-grid > div {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    padding: $space-2;
    border-radius: $radius-md;
    background: $color-bg-subtle;
  }

  .mobile-kv-grid span {
    color: $color-text-secondary;
    font-size: 11px;
  }

  .mobile-kv-grid strong {
    overflow: hidden;
    font-weight: $font-weight-semibold;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mobile-listing-collapse {
    border: 0;
  }

  .mobile-listing-collapse :deep(.el-collapse-item__header) {
    height: 36px;
    border: 0;
    font-size: $font-size-xs;
  }

  .mobile-listing-collapse :deep(.el-collapse-item__wrap) {
    border: 0;
  }

  .mobile-listing-collapse :deep(.el-collapse-item__content) {
    padding: 0;
  }

  .mobile-listing-list {
    display: flex;
    flex-direction: column;
    gap: $space-2;
  }

  .mobile-listing-item {
    padding: $space-2;
    border: 1px solid $color-border-default;
    border-radius: $radius-md;
  }

  .mobile-listing-item__head,
  .mobile-listing-item__sales {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: $space-2;
  }

  .mobile-listing-item__sku,
  .mobile-listing-item__sales {
    margin-top: $space-1;
    color: $color-text-secondary;
    font-size: $font-size-xs;
  }
}
</style>
