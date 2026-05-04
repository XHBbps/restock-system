<template>
  <PageSectionCard title="出库">
    <template #actions>
      <el-input
        v-model="filters.out_warehouse_no"
        placeholder="出库单号"
        clearable
        style="width: 200px"
        @keyup.enter="reloadFirstPage"
        @clear="reloadFirstPage"
      />
      <el-input
        v-model="filters.sku"
        placeholder="商品 SKU"
        clearable
        style="width: 200px"
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
        @clear="reloadFirstPage"
      >
        <el-option v-for="c in countryOptions" :key="c.code" :label="c.label" :value="c.code" />
      </el-select>
      <el-select
        v-model="filters.type_name"
        placeholder="出库单类型"
        clearable
        filterable
        style="width: 160px"
        @change="reloadFirstPage"
        @clear="reloadFirstPage"
      >
        <el-option v-for="type in typeOptions" :key="type" :label="type" :value="type" />
      </el-select>
      <el-select
        v-model="filters.is_in_transit"
        placeholder="状态"
        clearable
        style="width: 130px"
        @change="reloadFirstPage"
        @clear="reloadFirstPage"
      >
        <el-option label="在途" :value="true" />
        <el-option label="完结" :value="false" />
      </el-select>
    </template>

    <el-table
      v-if="!isMobile"
      v-loading="loading"
      :data="rows"
      row-key="saihuOutRecordId"
      table-layout="fixed"
      @sort-change="handleSortChange"
    >
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="expand-panel">
            <div class="expand-title">出库单明细（{{ row.items.length }} 项）</div>
            <el-table :data="row.items" size="small" class="detail-table" table-layout="auto">
              <el-table-column label="商品SKU" prop="commoditySku" min-width="240" show-overflow-tooltip />
              <el-table-column label="商品ID" prop="commodityId" min-width="180" show-overflow-tooltip />
              <el-table-column label="可用数" prop="goods" width="120" align="right" sortable show-overflow-tooltip />
              <el-table-column label="采购单价" prop="perPurchase" width="140" align="right" show-overflow-tooltip>
                <template #default="{ row: item }">
                  {{ item.perPurchase ?? '-' }}
                </template>
              </el-table-column>
            </el-table>
            <div class="expand-meta">
              <span>出库单号：<code>{{ row.outWarehouseNo || '-' }}</code></span>
              <span>备注：<code>{{ row.remark || '-' }}</code></span>
              <span>最后观测：<code>{{ formatShortTime(row.lastSeenAt) }}</code></span>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="出库单ID" prop="saihuOutRecordId" min-width="220" sortable="custom" show-overflow-tooltip />
      <el-table-column label="出库仓库ID" prop="warehouseId" min-width="180" sortable="custom" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="mono">{{ row.warehouseId || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="目标国家" prop="targetCountry" width="110" sortable="custom">
        <template #default="{ row }">
          <el-tag v-if="row.targetCountry" size="small">{{ row.targetCountry }}</el-tag>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" prop="updateTime" width="160" sortable="custom" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="muted mono">{{ formatUpdateTime(row.updateTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="同步时间" prop="lastSeenAt" width="160" sortable="custom" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="muted mono">{{ formatUpdateTime(row.lastSeenAt) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="出库单类型" prop="typeName" min-width="220" sortable="custom">
        <template #default="{ row }">
          <el-tag v-if="row.typeName" type="info" size="small">{{ row.typeName }}</el-tag>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" prop="status" width="96" sortable="custom">
        <template #default="{ row }">
          <el-tag :type="getOutRecordTransitStatusMeta(row.isInTransit).tagType" size="small">
            {{ getOutRecordTransitStatusMeta(row.isInTransit).label }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>

    <MobileRecordList
      v-else
      :items="rows"
      :loading="loading"
      row-key="saihuOutRecordId"
      empty-text="暂无出库记录"
    >
      <template #default="{ item: row }">
        <div class="mobile-out-record-card">
          <div class="mobile-card-head">
            <div class="meta-stack">
              <strong class="mono">{{ row.saihuOutRecordId }}</strong>
              <span class="meta-sub">{{ row.warehouseId || '-' }}</span>
            </div>
            <el-tag :type="getOutRecordTransitStatusMeta(row.isInTransit).tagType" size="small">
              {{ getOutRecordTransitStatusMeta(row.isInTransit).label }}
            </el-tag>
          </div>
          <div class="mobile-card-meta">
            <el-tag v-if="row.targetCountry" size="small">{{ row.targetCountry }}</el-tag>
            <span v-else class="muted">目标国家 -</span>
            <el-tag v-if="row.typeName" type="info" size="small">{{ row.typeName }}</el-tag>
          </div>
          <div class="mobile-kv-grid">
            <div>
              <span>明细数</span>
              <strong>{{ row.items.length }}</strong>
            </div>
            <div>
              <span>更新时间</span>
              <strong class="mono">{{ formatUpdateTime(row.updateTime) }}</strong>
            </div>
            <div class="mobile-kv-grid__wide">
              <span>同步时间</span>
              <strong class="mono">{{ formatUpdateTime(row.lastSeenAt) }}</strong>
            </div>
          </div>
          <el-collapse v-if="row.items.length > 0" class="mobile-detail-collapse">
            <el-collapse-item :title="`出库明细（${row.items.length}）`" name="items">
              <div class="mobile-out-items">
                <div v-for="item in row.items" :key="`${row.saihuOutRecordId}-${item.commoditySku}-${item.commodityId}`" class="mobile-out-item">
                  <div class="mobile-out-item__sku mono">{{ item.commoditySku }}</div>
                  <div class="mobile-out-item__meta">
                    <span>商品ID {{ item.commodityId || '-' }}</span>
                    <span>可用 {{ item.goods }}</span>
                    <span>采购单价 {{ item.perPurchase ?? '-' }}</span>
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
      :page-sizes="[20, 50, 100]"
      @current-change="handlePageChange"
      @size-change="handlePageSizeChange"
    />
  </PageSectionCard>
</template>

<script setup lang="ts">
import { listOutRecords, listOutRecordTypes, type DataOutRecord } from '@/api/data'
import { getCountryOptions, type CountryOption } from '@/api/config'
import MobileRecordList from '@/components/MobileRecordList.vue'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { useResponsive } from '@/composables/useResponsive'
import { getActionErrorMessage } from '@/utils/apiError'
import { COUNTRY_OPTIONS } from '@/utils/countries'
import { formatShortTime, formatUpdateTime } from '@/utils/format'
import { getOutRecordTransitStatusMeta } from '@/utils/status'
import { normalizeSortOrder, type SortChangeEvent, type SortState } from '@/utils/tableSort'
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

const rows = ref<DataOutRecord[]>([])
const { isMobile } = useResponsive()
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const loading = ref(false)
const countryOptions = ref<CountryOption[]>(
  COUNTRY_OPTIONS.map((option) => ({
    ...option,
    builtin: true,
    observed: false,
    can_be_eu_member: !['EU', 'ZZ'].includes(option.code),
  })),
)
const typeOptions = ref<string[]>([])
const sortState = ref<SortState>({ prop: 'updateTime', order: 'desc' })
const filters = reactive({
  out_warehouse_no: '',
  sku: '',
  country: '',
  type_name: '',
  is_in_transit: undefined as boolean | undefined,
})

async function reload(resetPage = false): Promise<void> {
  if (resetPage) {
    page.value = 1
  }
  loading.value = true
  try {
    const resp = await listOutRecords({
      out_warehouse_no: filters.out_warehouse_no || undefined,
      sku: filters.sku || undefined,
      country: filters.country || undefined,
      type_name: filters.type_name || undefined,
      is_in_transit: filters.is_in_transit,
      page: page.value,
      page_size: pageSize.value,
      sort_by: sortState.value.prop,
      sort_order: sortState.value.order,
    })
    rows.value = resp.items
    total.value = resp.total
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载失败'))
  } finally {
    loading.value = false
  }
}

function handleSortChange({ prop, order }: SortChangeEvent): void {
  const normalizedOrder = normalizeSortOrder(order)
  sortState.value = normalizedOrder && prop
    ? { prop, order: normalizedOrder }
    : { prop: 'updateTime', order: 'desc' }
  void reload(true)
}

async function loadTypeOptions(): Promise<void> {
  try {
    typeOptions.value = await listOutRecordTypes()
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载出库单类型失败'))
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
  void loadTypeOptions()
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
.expand-panel {
  padding: $space-3 $space-4;
  background: $color-bg-subtle;
  border-radius: $radius-md;
}

.expand-title {
  margin-bottom: $space-2;
  color: $color-text-secondary;
  font-size: $font-size-xs;
  font-weight: $font-weight-semibold;
  letter-spacing: $tracking-wider;
  text-transform: uppercase;
}

.expand-meta {
  display: flex;
  flex-wrap: wrap;
  gap: $space-3;
  margin-top: $space-2;
  font-size: $font-size-xs;
  color: $color-text-secondary;
}

.expand-meta code {
  font-family: $font-family-mono;
  background: $color-bg-card;
  padding: 2px 6px;
  border-radius: $radius-sm;
  border: 1px solid $color-border-default;
}

.detail-table {
  width: 100%;
}

.detail-table :deep(.el-table__inner-wrapper),
.detail-table :deep(.el-scrollbar__view),
.detail-table :deep(.el-table__header),
.detail-table :deep(.el-table__body),
.detail-table :deep(table) {
  width: 100% !important;
}

.muted {
  color: $color-text-secondary;
}

.mono {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
}

@media (max-width: 767px) {
  .mobile-out-record-card {
    display: flex;
    flex-direction: column;
    gap: $space-3;
  }

  .mobile-card-head,
  .mobile-card-meta {
    display: flex;
    align-items: center;
    gap: $space-2;
  }

  .mobile-card-head {
    justify-content: space-between;
  }

  .mobile-card-meta {
    flex-wrap: wrap;
  }

  .mobile-kv-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
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
  .mobile-out-item__meta {
    color: $color-text-secondary;
    font-size: $font-size-xs;
  }

  .mobile-kv-grid strong {
    min-width: 0;
    overflow: hidden;
    font-weight: $font-weight-medium;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mobile-kv-grid__wide {
    grid-column: 1 / -1;
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

  .mobile-out-items {
    display: flex;
    flex-direction: column;
    gap: $space-2;
  }

  .mobile-out-item {
    padding: $space-2;
    border: 1px solid $color-border-default;
    border-radius: $radius-md;
  }

  .mobile-out-item__sku {
    overflow: hidden;
    font-weight: $font-weight-semibold;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mobile-out-item__meta {
    display: flex;
    flex-wrap: wrap;
    gap: $space-2;
    margin-top: $space-1;
  }
}
</style>
