<template>
  <PageSectionCard title="其他出库（在途观测）">
    <template #actions>
      <el-input
        v-model="filters.sku"
        placeholder="commoditySku"
        clearable
        style="width: 200px"
        @keyup.enter="reload"
        @clear="reload"
      />
      <el-select v-model="filters.country" placeholder="国家" clearable filterable style="width: 140px" @change="reload">
        <el-option v-for="c in COUNTRY_OPTIONS" :key="c.code" :label="c.code" :value="c.code" />
      </el-select>
      <el-select v-model="filters.is_in_transit" placeholder="状态" style="width: 130px" @change="reload">
        <el-option label="在途中" :value="true" />
        <el-option label="已消失" :value="false" />
      </el-select>
    </template>

    <el-table v-loading="loading" :data="pagedRows" row-key="saihuOutRecordId" @sort-change="handleSortChange">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="expand-panel">
            <div class="expand-title">出库单明细（{{ row.items.length }} 项）</div>
            <el-table :data="row.items" size="small">
              <el-table-column label="商品 SKU" prop="commoditySku" sortable show-overflow-tooltip />
              <el-table-column label="商品数量" prop="goods" width="160" align="right" sortable show-overflow-tooltip />
            </el-table>
            <div class="expand-meta">
              备注：<code>{{ row.remark || '-' }}</code>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="出库单号" prop="outWarehouseNo" min-width="160" sortable="custom" show-overflow-tooltip />
      <el-table-column label="外部出库 ID" prop="saihuOutRecordId" width="160" sortable="custom" show-overflow-tooltip />
      <el-table-column label="目标仓" prop="targetWarehouseName" min-width="200" sortable="custom">
        <template #default="{ row }">
          <div class="meta-stack">
            <span>{{ row.targetWarehouseName || '-' }}</span>
            <span class="meta-sub">{{ row.targetWarehouseId || '未知' }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="目标国家" prop="targetCountry" width="90" align="center" sortable="custom">
        <template #default="{ row }">
          <el-tag v-if="row.targetCountry" size="small">{{ row.targetCountry }}</el-tag>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="明细数" prop="itemCount" width="90" align="right" sortable="custom" show-overflow-tooltip>
        <template #default="{ row }">{{ row.items.length }}</template>
      </el-table-column>
      <el-table-column label="观测总数" prop="goodsTotal" width="100" align="right" sortable="custom" show-overflow-tooltip>
        <template #default="{ row }">
          <strong>{{ sumGoods(row) }}</strong>
        </template>
      </el-table-column>
      <el-table-column label="状态" prop="status" width="100" sortable="custom">
        <template #default="{ row }">
          <el-tag v-if="row.isInTransit" type="success" size="small">在途中</el-tag>
          <el-tag v-else type="info" size="small">已消失</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最后同步" prop="lastSeenAt" width="160" sortable="custom" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="muted mono">{{ formatShortTime(row.lastSeenAt) }}</span>
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
import { COUNTRY_OPTIONS } from '@/utils/countries'
import { formatShortTime } from '@/utils/format'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { normalizeSortOrder, type SortChangeEvent, type SortState } from '@/utils/tableSort'
import { getActionErrorMessage } from '@/utils/apiError'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'

const rows = ref<DataOutRecord[]>([])
const page = ref(1)
const pageSize = ref(50)
const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return rows.value.slice(start, start + pageSize.value)
})
const loading = ref(false)
const sortState = ref<SortState>({ prop: 'lastSeenAt', order: 'desc' })
const filters = reactive({
  sku: '',
  country: '',
  is_in_transit: true as boolean | undefined,
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

function sumGoods(row: DataOutRecord): number {
  return row.items.reduce((sum, it) => sum + it.goods, 0)
}

function handleSortChange({ prop, order }: SortChangeEvent): void {
  const normalizedOrder = normalizeSortOrder(order)
  sortState.value = normalizedOrder && prop
    ? { prop, order: normalizedOrder }
    : { prop: 'lastSeenAt', order: 'desc' }
  page.value = 1
  void reload()
}

watch(
  () => [filters.sku, filters.country, filters.is_in_transit],
  () => { page.value = 1 },
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
  font-size: $font-size-xs;
  color: $color-text-secondary;
  font-weight: $font-weight-semibold;
  text-transform: uppercase;
  letter-spacing: $tracking-wider;
  margin-bottom: $space-2;
}

.expand-meta {
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

.meta-stack {
  display: flex;
  flex-direction: column;
}

.meta-sub {
  font-size: $font-size-xs;
  color: $color-text-secondary;
  font-family: $font-family-mono;
}

.muted {
  color: $color-text-secondary;
}

.mono {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
}
</style>
