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
        <el-option v-for="c in COUNTRY_OPTIONS" :key="c.code" :label="c.code" :value="c.code" />
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
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { COUNTRY_OPTIONS } from '@/utils/countries'
import { formatShortTime, formatUpdateTime } from '@/utils/format'
import { getOutRecordTransitStatusMeta } from '@/utils/status'
import { normalizeSortOrder, type SortChangeEvent, type SortState } from '@/utils/tableSort'
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

const rows = ref<DataOutRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const loading = ref(false)
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

onMounted(() => {
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
</style>
