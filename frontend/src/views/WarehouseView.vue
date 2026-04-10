<template>
  <PageSectionCard title="仓库配置">
    <el-table v-loading="loading" :data="pagedRows" style="width: 100%" :scrollbar-always-on="true">
      <el-table-column label="仓库名称" prop="name" min-width="200" sortable show-overflow-tooltip />
      <el-table-column label="仓库 ID" prop="id" width="140" sortable show-overflow-tooltip />
      <el-table-column label="类型" prop="type" width="120" align="center" sortable :sort-method="(a: Warehouse, b: Warehouse) => (TYPE_SORT_ORDER[a.type] ?? 9) - (TYPE_SORT_ORDER[b.type] ?? 9)">
        <template #default="{ row }">
          <el-tag :type="warehouseTypeTag(row.type)" size="small">
            {{ warehouseTypeLabel(row.type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="补货站点" min-width="200">
        <template #default="{ row }">
          <template v-if="row.replenish_site_raw">
            <el-tag
              v-for="site in parseSites(row.replenish_site_raw)"
              :key="site"
              size="small"
              style="margin-right: 4px; margin-bottom: 2px"
            >
              {{ site }}
            </el-tag>
          </template>
          <span v-else class="hint">-</span>
        </template>
      </el-table-column>
      <el-table-column label="所属国家" width="200">
        <template #default="{ row }">
          <el-select
            v-model="row.country"
            filterable
            placeholder="选择国家"
            style="width: 170px"
            @change="(val: string) => save(row, val)"
          >
            <el-option
              v-for="opt in countryOptions"
              :key="opt.code"
              :label="opt.label"
              :value="opt.code"
            />
          </el-select>
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
import { listWarehouses, patchWarehouseCountry, type Warehouse } from '@/api/config'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { COUNTRY_OPTIONS } from '@/utils/countries'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

const rows = ref<Warehouse[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)

const countryOptions = COUNTRY_OPTIONS

const WAREHOUSE_TYPE_MAP: Record<number, string> = {
  [-1]: '虚拟仓',
  0: '默认仓',
  1: '国内仓库',
  2: 'FBA仓',
  3: '海外仓',
}

// 默认排序优先级: 默认仓 → 国内仓 → 海外仓 → FBA仓 → 虚拟仓
const TYPE_SORT_ORDER: Record<number, number> = { 0: 0, 1: 1, 3: 2, 2: 3, [-1]: 4 }

function sortByType(list: Warehouse[]): Warehouse[] {
  return [...list].sort((a, b) => (TYPE_SORT_ORDER[a.type] ?? 9) - (TYPE_SORT_ORDER[b.type] ?? 9))
}

function warehouseTypeLabel(type: number): string {
  return WAREHOUSE_TYPE_MAP[type] ?? `未知(${type})`
}

function warehouseTypeTag(type: number): 'success' | 'warning' | 'info' | 'danger' | '' {
  switch (type) {
    case 1: return 'success'
    case 2: return ''
    case 3: return 'warning'
    case -1: return 'info'
    default: return 'info'
  }
}

function parseSites(raw: string): string[] {
  return raw.split(/[,;，；\s]+/).filter((s) => s && s !== '-')
}

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return rows.value.slice(start, start + pageSize.value)
})

async function reload(): Promise<void> {
  loading.value = true
  try {
    rows.value = sortByType(await listWarehouses())
  } finally {
    loading.value = false
  }
}

async function save(row: Warehouse, value: string): Promise<void> {
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
.hint {
  color: $color-text-secondary;
  font-size: $font-size-xs;
}
</style>
