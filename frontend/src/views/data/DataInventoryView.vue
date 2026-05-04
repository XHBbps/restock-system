<template>
  <PageSectionCard title="库存明细">
    <template #actions>
      <el-input
        v-model="filters.sku"
        placeholder="commoditySku"
        clearable
        style="width: 220px"
        @keyup.enter="reloadFirstPage"
        @clear="reloadFirstPage"
      />
      <el-select
        v-model="filters.country"
        placeholder="国家"
        clearable
        filterable
        style="width: 140px"
        @change="reloadFirstPage"
      >
        <el-option v-for="c in countryOptions" :key="c.code" :label="c.label" :value="c.code" />
      </el-select>
      <el-select
        v-model="filters.is_package"
        placeholder="未匹配"
        style="width: 120px"
        @change="reloadFirstPage"
      >
        <el-option label="全部" value="" />
        <el-option label="未匹配" :value="true" />
        <el-option label="已匹配" :value="false" />
      </el-select>
      <el-switch v-model="filters.only_nonzero" active-text="仅非零" @change="reloadFirstPage" />
    </template>

    <el-table v-if="!isMobile" v-loading="loading" :data="warehouseGroups" row-key="warehouseId">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="expand-wrapper">
            <el-table :data="row.items" size="small" :show-header="true">
              <el-table-column label="SKU" min-width="200">
                <template #default="{ row: item }">
                  <SkuCard
                    :sku="item.commoditySku"
                    :name="item.commodityName"
                    :image="item.mainImage"
                  />
                </template>
              </el-table-column>
              <el-table-column label="国家" width="80" align="center">
                <template #default="{ row: item }">
                  <el-tag v-if="item.country" size="small">{{ item.country }}</el-tag>
                  <span v-else class="muted">-</span>
                </template>
              </el-table-column>
              <el-table-column label="未匹配" width="80" align="center">
                <template #default="{ row: item }">
                  <span class="package-marker" :title="item.isPackage ? '未匹配' : '已匹配'">
                    {{ item.isPackage ? '●' : '○' }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="可用库存" prop="stockAvailable" width="120" align="right" />
              <el-table-column label="占用库存" prop="stockOccupy" width="120" align="right" />
              <el-table-column label="同步时间" width="168">
                <template #default="{ row: item }">
                  <span class="muted mono">{{ formatUpdateTime(item.updatedAt) }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="仓库" min-width="260">
        <template #default="{ row }">
          <div class="meta-stack">
            <strong>{{ row.warehouseName }}</strong>
            <span class="meta-sub">{{ row.warehouseId }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="100" align="center">
        <template #default="{ row }">
          {{ warehouseTypeLabel(row.warehouseType) }}
        </template>
      </el-table-column>
      <el-table-column label="SKU 数" prop="skuCount" width="100" align="right" />
      <el-table-column label="可用库存合计" prop="totalAvailable" width="140" align="right">
        <template #default="{ row }">
          <strong>{{ row.totalAvailable }}</strong>
        </template>
      </el-table-column>
      <el-table-column label="占用库存合计" prop="totalOccupy" width="140" align="right" />
    </el-table>

    <MobileRecordList
      v-else
      :items="warehouseGroups"
      :loading="loading"
      row-key="warehouseId"
      empty-text="暂无库存"
    >
      <template #default="{ item: row }">
        <div class="mobile-inventory-card">
          <div class="mobile-card-head">
            <div class="meta-stack">
              <strong>{{ row.warehouseName }}</strong>
              <span class="meta-sub">{{ row.warehouseId }}</span>
            </div>
            <el-tag size="small" type="info">{{ warehouseTypeLabel(row.warehouseType) }}</el-tag>
          </div>
          <div class="mobile-kv-grid">
            <div>
              <span>SKU 数</span>
              <strong>{{ row.skuCount }}</strong>
            </div>
            <div>
              <span>可用库存</span>
              <strong>{{ row.totalAvailable }}</strong>
            </div>
            <div>
              <span>占用库存</span>
              <strong>{{ row.totalOccupy }}</strong>
            </div>
          </div>
          <el-collapse v-if="row.items.length > 0" class="mobile-detail-collapse">
            <el-collapse-item :title="`库存明细（${row.items.length}）`" name="items">
              <div class="mobile-inventory-items">
                <div v-for="item in row.items" :key="`${item.warehouseId}-${item.commoditySku}`" class="mobile-inventory-item">
                  <SkuCard :sku="item.commoditySku" :name="item.commodityName" :image="item.mainImage" />
                  <div class="mobile-inventory-item__meta">
                    <el-tag v-if="item.country" size="small">{{ item.country }}</el-tag>
                    <span v-else class="muted">-</span>
                    <span>{{ item.isPackage ? '未匹配' : '已匹配' }}</span>
                    <span>可用 {{ item.stockAvailable }}</span>
                    <span>占用 {{ item.stockOccupy }}</span>
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
      :page-sizes="[10, 20, 50]"
      @current-change="handlePageChange"
      @size-change="handlePageSizeChange"
    />
  </PageSectionCard>
</template>

<script setup lang="ts">
import { listInventoryWarehouseGroups, type DataInventoryWarehouseGroup } from '@/api/data'
import { getCountryOptions, type CountryOption } from '@/api/config'
import MobileRecordList from '@/components/MobileRecordList.vue'
import PageSectionCard from '@/components/PageSectionCard.vue'
import SkuCard from '@/components/SkuCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { useResponsive } from '@/composables/useResponsive'
import { getActionErrorMessage } from '@/utils/apiError'
import { COUNTRY_OPTIONS } from '@/utils/countries'
import { formatUpdateTime } from '@/utils/format'
import { warehouseTypeLabel } from '@/utils/warehouse'
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

const warehouseGroups = ref<DataInventoryWarehouseGroup[]>([])
const { isMobile } = useResponsive()
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const countryOptions = ref<CountryOption[]>(
  COUNTRY_OPTIONS.map((option) => ({
    ...option,
    builtin: true,
    observed: false,
    can_be_eu_member: !['EU', 'ZZ'].includes(option.code),
  })),
)
const filters = reactive({
  sku: '',
  country: '',
  only_nonzero: true,
  is_package: '' as '' | boolean
})

async function reload(resetPage = false): Promise<void> {
  if (resetPage) {
    page.value = 1
  }
  loading.value = true
  try {
    const resp = await listInventoryWarehouseGroups({
      sku: filters.sku || undefined,
      country: filters.country || undefined,
      only_nonzero: filters.only_nonzero,
      is_package: typeof filters.is_package === 'boolean' ? filters.is_package : undefined,
      page: page.value,
      page_size: pageSize.value
    })
    warehouseGroups.value = resp.items
    total.value = resp.total
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载失败'))
  } finally {
    loading.value = false
  }
}

async function loadCountryOptions(): Promise<void> {
  try {
    const resp = await getCountryOptions()
    countryOptions.value = resp.items
  } catch {
    // 保留内置选项作为降级。
  }
}

onMounted(() => {
  void loadCountryOptions()
  void reload()
})

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

.meta-stack {
  display: flex;
  flex-direction: column;
}

.meta-sub {
  color: $color-text-secondary;
  font-size: $font-size-xs;
}

.muted {
  color: $color-text-secondary;
}

.mono {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
}

.package-marker {
  display: inline-block;
  font-size: 2em;
  line-height: 1;
}

@media (max-width: 767px) {
  .mobile-inventory-card {
    display: flex;
    flex-direction: column;
    gap: $space-3;
  }

  .mobile-card-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: $space-3;
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

  .mobile-kv-grid span,
  .mobile-inventory-item__meta {
    color: $color-text-secondary;
    font-size: $font-size-xs;
  }

  .mobile-kv-grid strong {
    font-weight: $font-weight-semibold;
  }

  .mobile-detail-collapse {
    border: 0;
  }

  .mobile-detail-collapse :deep(.el-collapse-item__header),
  .mobile-detail-collapse :deep(.el-collapse-item__wrap) {
    border: 0;
  }

  .mobile-detail-collapse :deep(.el-collapse-item__header) {
    height: 36px;
    font-size: $font-size-xs;
  }

  .mobile-detail-collapse :deep(.el-collapse-item__content) {
    padding: 0;
  }

  .mobile-inventory-items {
    display: flex;
    flex-direction: column;
    gap: $space-2;
  }

  .mobile-inventory-item {
    display: flex;
    flex-direction: column;
    gap: $space-2;
    padding: $space-2;
    border: 1px solid $color-border-default;
    border-radius: $radius-md;
  }

  .mobile-inventory-item__meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: $space-2;
  }
}
</style>
