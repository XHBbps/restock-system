<template>
  <PageSectionCard title="库存明细">
    <template #actions>
      <el-input
        v-model="filters.sku"
        placeholder="commoditySku"
        clearable
        style="width: 220px"
        @keyup.enter="reload"
        @clear="reload"
      />
      <el-select v-model="filters.country" placeholder="国家" clearable filterable style="width: 140px" @change="reload">
        <el-option v-for="c in COUNTRY_OPTIONS" :key="c.code" :label="c.code" :value="c.code" />
      </el-select>
      <el-switch v-model="filters.only_nonzero" active-text="仅非零" @change="reload" />
    </template>

    <el-table v-loading="loading" :data="pagedGroups" row-key="warehouseId">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="expand-wrapper">
            <el-table :data="row.items" size="small" :show-header="true">
              <el-table-column label="SKU" min-width="200">
                <template #default="{ row: item }">
                  <SkuCard :sku="item.commoditySku" :name="item.commodityName" :image="item.mainImage" />
                </template>
              </el-table-column>
              <el-table-column label="国家" width="80" align="center">
                <template #default="{ row: item }">
                  <el-tag v-if="item.country" size="small">{{ item.country }}</el-tag>
                  <span v-else class="muted">-</span>
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

    <TablePaginationBar
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="warehouseGroups.length"
      :page-sizes="[10, 20, 50]"
    />
  </PageSectionCard>
</template>

<script setup lang="ts">
import { listInventory, type DataInventoryItem } from '@/api/data'
import { COUNTRY_OPTIONS } from '@/utils/countries'
import { formatUpdateTime } from '@/utils/format'
import { warehouseTypeLabel } from '@/utils/warehouse'
import PageSectionCard from '@/components/PageSectionCard.vue'
import SkuCard from '@/components/SkuCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'

interface WarehouseGroup {
  warehouseId: string
  warehouseName: string
  warehouseType: number
  skuCount: number
  totalAvailable: number
  totalOccupy: number
  items: DataInventoryItem[]
}

const rows = ref<DataInventoryItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filters = reactive({
  sku: '',
  country: '',
  only_nonzero: true,
})

const warehouseGroups = computed<WarehouseGroup[]>(() => {
  const map = new Map<string, WarehouseGroup>()
  for (const item of rows.value) {
    let group = map.get(item.warehouseId)
    if (!group) {
      group = {
        warehouseId: item.warehouseId,
        warehouseName: item.warehouseName,
        warehouseType: item.warehouseType,
        skuCount: 0,
        totalAvailable: 0,
        totalOccupy: 0,
        items: [],
      }
      map.set(item.warehouseId, group)
    }
    group.skuCount++
    group.totalAvailable += item.stockAvailable
    group.totalOccupy += item.stockOccupy
    group.items.push(item)
  }
  return [...map.values()]
})

const pagedGroups = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return warehouseGroups.value.slice(start, start + pageSize.value)
})

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listInventory({
      sku: filters.sku || undefined,
      country: filters.country || undefined,
      only_nonzero: filters.only_nonzero,
      page: 1,
      page_size: 5000,
    })
    rows.value = resp.items
    page.value = 1
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载失败'))
  } finally {
    loading.value = false
  }
}

watch(
  () => [filters.sku, filters.country, filters.only_nonzero],
  () => { page.value = 1 },
)

onMounted(reload)
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
</style>
