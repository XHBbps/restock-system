<template>
  <PageSectionCard title="出库记录">
    <template #actions>
      <el-input
        v-model="filters.sku"
        placeholder="商品 SKU"
        clearable
        style="width: 200px"
        @keyup.enter="reload"
        @clear="reload"
      />
      <el-select
        v-model="filters.country"
        placeholder="国家"
        clearable
        filterable
        style="width: 140px"
        @change="reload"
      >
        <el-option v-for="c in COUNTRY_OPTIONS" :key="c.code" :label="c.code" :value="c.code" />
      </el-select>
      <el-select v-model="filters.is_in_transit" placeholder="状态" style="width: 130px" @change="reload">
        <el-option label="在途" :value="true" />
        <el-option label="完结" :value="false" />
      </el-select>
    </template>

    <el-table v-loading="loading" :data="pagedRows" row-key="saihuOutRecordId" @sort-change="handleSortChange">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="expand-panel">
            <div class="expand-title">出库单明细（{{ row.items.length }} 项）</div>
            <el-table :data="row.items" size="small">
              <el-table-column label="商品id" prop="commodityId" min-width="160" show-overflow-tooltip />
              <el-table-column label="商品sku" prop="commoditySku" min-width="160" show-overflow-tooltip />
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
      <el-table-column label="出库单id" prop="saihuOutRecordId" min-width="180" sortable="custom" show-overflow-tooltip />
      <el-table-column label="出库仓库id" prop="warehouseId" min-width="160" sortable="custom" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="mono">{{ row.warehouseId || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" prop="updateTime" width="168" sortable="custom" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="muted mono">{{ formatShortTime(row.updateTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="出库单类型" prop="typeName" min-width="180" sortable="custom" show-overflow-tooltip>
        <template #default="{ row }">
          <span>{{ row.typeName || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" prop="status" width="100" sortable="custom">
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
      :total="rows.length"
      :page-sizes="[20, 50, 100]"
    />
  </PageSectionCard>
</template>

<script setup lang="ts">
import { listOutRecords, type DataOutRecord } from '@/api/data'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { COUNTRY_OPTIONS } from '@/utils/countries'
import { formatShortTime } from '@/utils/format'
import { getOutRecordTransitStatusMeta } from '@/utils/status'
import { normalizeSortOrder, type SortChangeEvent, type SortState } from '@/utils/tableSort'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'

const rows = ref<DataOutRecord[]>([])
const page = ref(1)
const pageSize = ref(50)
const loading = ref(false)
const sortState = ref<SortState>({ prop: 'updateTime', order: 'desc' })
const filters = reactive({
  sku: '',
  country: '',
  is_in_transit: true as boolean | undefined,
})

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return rows.value.slice(start, start + pageSize.value)
})

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listOutRecords({
      sku: filters.sku || undefined,
      country: filters.country || undefined,
      is_in_transit: filters.is_in_transit,
      page: 1,
      page_size: 5000,
      sort_by: sortState.value.prop,
      sort_order: sortState.value.order,
    })
    rows.value = resp.items
    page.value = 1
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
  page.value = 1
  void reload()
}

watch(
  () => [filters.sku, filters.country, filters.is_in_transit],
  () => {
    page.value = 1
  },
)

onMounted(reload)
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

.muted {
  color: $color-text-secondary;
}

.mono {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
}
</style>
