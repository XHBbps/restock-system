# Inventory Warehouse Grouping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the inventory page to group rows by warehouse with expand/collapse, matching the product page pattern.

**Architecture:** Frontend-only change. The existing `/api/data/inventory` API returns flat rows with `warehouseId`/`warehouseName`. The frontend will group these by warehouse and render as an expandable table (parent = warehouse row, child = SKU inventory rows). No backend changes needed.

**Tech Stack:** Vue 3, Element Plus `el-table` with `type="expand"`, TypeScript

---

### Task 1: Rewrite DataInventoryView.vue template — warehouse-grouped expand table

**Files:**
- Modify: `frontend/src/views/data/DataInventoryView.vue`

- [ ] **Step 1: Replace the template with warehouse-grouped expand table**

Replace the entire `<template>` section. The new structure:
- Main table: one row per warehouse (name, country, type, total available, total occupy, SKU count)
- Expand row: nested table showing all SKU inventory rows for that warehouse

```vue
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
      <el-input
        v-model="filters.country"
        placeholder="国家（CN/US/...）"
        clearable
        maxlength="2"
        style="width: 140px"
        @keyup.enter="reload"
        @clear="reload"
      />
      <el-switch v-model="filters.only_nonzero" active-text="仅非零" @change="reload" />
    </template>

    <el-table v-loading="loading" :data="warehouseGroups" row-key="warehouseId">
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
              <el-table-column label="更新时间" width="160">
                <template #default="{ row: item }">
                  <span class="muted mono">{{ formatTime(item.updatedAt) }}</span>
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
      :total="total"
      :page-sizes="[20, 50, 100, 200]"
      @current-change="reload"
      @size-change="reload"
    />
  </PageSectionCard>
</template>
```

- [ ] **Step 2: Replace the script section with grouping logic**

```vue
<script setup lang="ts">
import { listInventory, type DataInventoryItem } from '@/api/data'
import PageSectionCard from '@/components/PageSectionCard.vue'
import SkuCard from '@/components/SkuCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import dayjs from 'dayjs'
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
const total = ref(0)
const page = ref(1)
const pageSize = ref(200)
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

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listInventory({
      sku: filters.sku || undefined,
      country: filters.country || undefined,
      only_nonzero: filters.only_nonzero,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = resp.items
    total.value = resp.total
  } finally {
    loading.value = false
  }
}

function warehouseTypeLabel(type: number): string {
  const labels: Record<number, string> = { '-1': '虚拟', 0: '默认', 1: '国内', 2: 'FBA', 3: '海外' }
  return labels[type] ?? `类型${type}`
}

function formatTime(value: string): string {
  return dayjs(value).format('MM-DD HH:mm')
}

watch(
  () => [filters.sku, filters.country, filters.only_nonzero],
  () => { page.value = 1 },
)

onMounted(reload)
</script>
```

- [ ] **Step 3: Replace the style section**

```vue
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
```

- [ ] **Step 4: Verify in browser**

1. Navigate to `/data/inventory`
2. Confirm table shows warehouse rows with expand arrows
3. Click expand on a warehouse → see SKU inventory rows inside
4. Verify SKU search and country filter still work
5. Verify "仅非零" toggle still works
6. Verify pagination works

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/data/DataInventoryView.vue
git commit -m "feat: group inventory page by warehouse with expand/collapse"
```
