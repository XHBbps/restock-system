<template>
  <PageSectionCard title="仓库">
    <el-table v-loading="loading" :data="pagedRows" style="width: 100%" :scrollbar-always-on="true">
      <el-table-column label="仓库名称" prop="name" min-width="200" sortable show-overflow-tooltip />
      <el-table-column label="仓库 ID" prop="id" width="100" sortable show-overflow-tooltip />
      <el-table-column label="类型" prop="type" width="100" align="center" sortable :sort-method="sortByTypeMethod">
        <template #default="{ row }">
          <el-tag :type="warehouseTypeTag(row.type)" size="small">
            {{ warehouseTypeLabel(row.type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="补货站点" min-width="200">
        <template #default="{ row }">
          <div v-if="parseSites(row.replenishSite).length" class="site-tags" :title="row.replenishSite">
            <el-tag
              v-for="site in parseSites(row.replenishSite)"
              :key="site"
              size="small"
              class="site-tag"
            >
              {{ site }}
            </el-tag>
          </div>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="所属国家" width="200">
        <template #default="{ row }">
          <el-select
            v-model="row.country"
            filterable
            placeholder="选择国家"
            style="width: 170px"
            @change="(val: string) => saveCountry(row, val)"
          >
            <el-option
              v-for="opt in COUNTRY_OPTIONS"
              :key="opt.code"
              :label="opt.label"
              :value="opt.code"
            />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="最近同步" width="140">
        <template #default="{ row }">
          <span class="muted mono">{{ formatTime(row.lastSyncAt) }}</span>
        </template>
      </el-table-column>
    </el-table>

    <TablePaginationBar
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="rows.length"
    />
  </PageSectionCard>
</template>

<script setup lang="ts">
import { listDataWarehouses, type DataWarehouse } from '@/api/data'
import { patchWarehouseCountry } from '@/api/config'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { COUNTRY_OPTIONS } from '@/utils/countries'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

const rows = ref<DataWarehouse[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)

const WAREHOUSE_TYPE_MAP: Record<number, string> = {
  [-1]: '虚拟仓',
  0: '默认仓',
  1: '国内仓库',
  2: 'FBA仓',
  3: '海外仓',
}

const TYPE_SORT_ORDER: Record<number, number> = { 0: 0, 1: 1, 3: 2, 2: 3, [-1]: 4 }

function warehouseTypeLabel(type: number): string {
  return WAREHOUSE_TYPE_MAP[type] ?? `未知(${type})`
}

function warehouseTypeTag(type: number): 'primary' | 'success' | 'warning' | 'info' | 'danger' | undefined {
  switch (type) {
    case 1: return 'success'
    case 2: return 'primary'
    case 3: return 'warning'
    case -1: return 'info'
    default: return 'info'
  }
}

function sortByTypeMethod(a: DataWarehouse, b: DataWarehouse): number {
  return (TYPE_SORT_ORDER[a.type] ?? 9) - (TYPE_SORT_ORDER[b.type] ?? 9)
}

function parseSites(raw: string | null): string[] {
  if (!raw) return []
  return raw.split(/[,;，；\s]+/).filter((s) => s && s !== '-')
}

function sortByType(list: DataWarehouse[]): DataWarehouse[] {
  return [...list].sort((a, b) => (TYPE_SORT_ORDER[a.type] ?? 9) - (TYPE_SORT_ORDER[b.type] ?? 9))
}

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return rows.value.slice(start, start + pageSize.value)
})

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listDataWarehouses()
    rows.value = sortByType(resp.items)
  } finally {
    loading.value = false
  }
}

function formatTime(value: string): string {
  return dayjs(value).format('MM-DD HH:mm')
}

async function saveCountry(row: DataWarehouse, value: string): Promise<void> {
  if (!value) return
  try {
    await patchWarehouseCountry(row.id, value)
    ElMessage.success(`${row.name} 已更新为 ${value}。`)
  } catch {
    ElMessage.error('更新失败。')
    await reload()
  }
}

onMounted(reload)
</script>

<style lang="scss" scoped>
.muted {
  color: $color-text-secondary;
}

.mono {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
}

.site-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  max-height: 56px;
  overflow: hidden;
}

.site-tag {
  flex-shrink: 0;
}
</style>
