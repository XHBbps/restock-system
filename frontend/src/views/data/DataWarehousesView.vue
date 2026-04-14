<template>
  <div class="data-warehouses-view">
    <PageSectionCard title="仓库" description="查看仓库主数据、补货站点和当前总库存。">
      <template #actions>
        <el-input v-model="filters.keyword" placeholder="搜索仓库名/ID" clearable style="width: 180px" />
        <el-select v-model="filters.type" placeholder="类型" clearable style="width: 120px">
          <el-option label="国内仓" :value="1" />
          <el-option label="FBA 仓" :value="2" />
          <el-option label="海外仓" :value="3" />
          <el-option label="默认仓" :value="0" />
          <el-option label="虚拟仓" :value="-1" />
        </el-select>
        <el-button v-if="auth.hasPermission('sync:operate')" :loading="refreshing" @click="refresh">刷新仓库</el-button>
      </template>

      <el-table
        v-loading="loading"
        :data="pagedRows"
        table-layout="fixed"
        style="width: 100%"
        :scrollbar-always-on="true"
        empty-text="暂无仓库数据"
        @sort-change="handleSortChange"
      >
        <el-table-column
          label="仓库名称"
          prop="name"
          min-width="200"
          sortable="custom"
          show-overflow-tooltip
        />
        <el-table-column
          label="仓库 ID"
          prop="id"
          width="120"
          sortable="custom"
          show-overflow-tooltip
        />
        <el-table-column label="类型" prop="type" width="100" align="center" sortable="custom">
          <template #default="{ row }">
            <el-tag :type="warehouseTypeTag(row.type)" size="small">
              {{ warehouseTypeLabel(row.type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="补货站点" min-width="200">
          <template #default="{ row }">
            <el-tooltip
              v-if="parseSites(row.replenishSite).length"
              placement="top"
              :content="parseSites(row.replenishSite).join('  ')"
              :hide-after="0"
            >
              <div class="site-tags">
                <el-tag
                  v-for="site in parseSites(row.replenishSite)"
                  :key="site"
                  size="small"
                >
                  {{ site }}
                </el-tag>
              </div>
            </el-tooltip>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="总库存" prop="totalStock" width="120" align="right" sortable="custom">
          <template #default="{ row }">
            <span class="mono">{{ formatStock(row.totalStock) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="所属国家" width="200">
          <template #default="{ row }">
            <el-select
              v-model="row.country"
              filterable
              clearable
              placeholder="选择国家"
              :disabled="!auth.hasPermission('config:edit')"
              style="width: 170px"
              @change="(val: string) => saveCountry(row, val)"
            >
              <el-option
                v-for="option in countryOptions"
                :key="option.code"
                :label="option.label"
                :value="option.code"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="同步时间" width="168">
          <template #default="{ row }">
            <span class="muted mono">{{ formatUpdateTime(row.lastSyncAt) }}</span>
          </template>
        </el-table-column>
      </el-table>

      <TablePaginationBar
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="filteredRows.length"
      />
    </PageSectionCard>

    <TaskProgress v-if="refreshTaskId" :task-id="refreshTaskId" @terminal="onRefreshDone" />
  </div>
</template>

<script setup lang="ts">
import { patchWarehouseCountry, refreshWarehouses } from '@/api/config'
import { listDataWarehouses, type DataWarehouse } from '@/api/data'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import { formatUpdateTime, clampPage } from '@/utils/format'
import { warehouseTypeLabel, warehouseTypeTag } from '@/utils/warehouse'
import { COUNTRY_OPTIONS } from '@/utils/countries'
import {
  applyLocalSort,
  compareNumber,
  compareText,
  normalizeSortOrder,
  type SortChangeEvent,
  type SortState,
} from '@/utils/tableSort'
import { useAuthStore } from '@/stores/auth'
import { getActionErrorMessage } from '@/utils/apiError'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'

const auth = useAuthStore()

const rows = ref<DataWarehouse[]>([])
const loading = ref(false)
const refreshing = ref(false)
const refreshTaskId = ref<number | null>(null)
const page = ref(1)
const pageSize = ref(10)
const sortState = ref<SortState>({})
const filters = reactive({
  keyword: '',
  type: undefined as number | undefined,
})

const countryOptions = COUNTRY_OPTIONS

const TYPE_SORT_ORDER: Record<number, number> = { 0: 0, 1: 1, 3: 2, 2: 3, [-1]: 4 }

function defaultWarehouseComparator(left: DataWarehouse, right: DataWarehouse): number {
  const typeCompare = compareNumber(TYPE_SORT_ORDER[left.type] ?? 9, TYPE_SORT_ORDER[right.type] ?? 9)
  if (typeCompare !== 0) return typeCompare
  return compareText(left.name, right.name)
}

function parseSites(raw: string | null): string[] {
  if (!raw) return []
  return raw.split(/[,;，；\s]+/).filter((item) => item && item !== '-')
}

function formatStock(value?: number | null): string {
  return Number(value || 0).toLocaleString('zh-CN')
}

const filteredRows = computed(() => {
  let result = rows.value
  if (filters.keyword) {
    const q = filters.keyword.toLowerCase()
    result = result.filter((r) => r.name.toLowerCase().includes(q) || r.id.toLowerCase().includes(q))
  }
  if (filters.type !== undefined) {
    result = result.filter((r) => r.type === filters.type)
  }
  return result
})

watch(() => [filters.keyword, filters.type], () => { page.value = 1 })

const sortedRows = computed(() =>
  applyLocalSort(
    filteredRows.value,
    sortState.value,
    {
      name: (left, right) => compareText(left.name, right.name),
      id: (left, right) => compareText(left.id, right.id),
      type: (left, right) => compareNumber(TYPE_SORT_ORDER[left.type] ?? 9, TYPE_SORT_ORDER[right.type] ?? 9),
      totalStock: (left, right) => compareNumber(left.totalStock, right.totalStock),
    },
    defaultWarehouseComparator,
  ),
)

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return sortedRows.value.slice(start, start + pageSize.value)
})

watch(
  [filteredRows, pageSize],
  () => {
    page.value = clampPage(page.value, filteredRows.value.length, pageSize.value)
  },
  { immediate: true },
)

async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listDataWarehouses()
    rows.value = resp.items
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载仓库列表失败'))
  } finally {
    loading.value = false
  }
}

async function refresh(): Promise<void> {
  refreshing.value = true
  try {
    const resp = await refreshWarehouses()
    refreshTaskId.value = resp.task_id
    ElMessage.success('仓库同步任务已入队')
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '仓库同步触发失败'))
  } finally {
    refreshing.value = false
  }
}

async function onRefreshDone(): Promise<void> {
  refreshTaskId.value = null
  await reload()
  ElMessage.success('仓库数据已刷新')
}

async function saveCountry(row: DataWarehouse, value: string): Promise<void> {
  try {
    await patchWarehouseCountry(row.id, value || null)
    ElMessage.success(value ? `${row.name} 已更新为 ${value}` : `${row.name} 已清除国家`)
    ElMessage.warning({
      message: '仓库国家已变更，建议重新生成补货建议单以确保数据准确。',
      duration: 5000,
    })
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '更新失败'))
    await reload()
  }
}

function handleSortChange({ prop, order }: SortChangeEvent): void {
  const normalizedOrder = normalizeSortOrder(order)
  sortState.value = normalizedOrder && prop ? { prop, order: normalizedOrder } : {}
  page.value = 1
}

onMounted(reload)
</script>

<style lang="scss" scoped>
.data-warehouses-view {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.muted {
  color: $color-text-secondary;
}

.mono {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
}

.site-tags {
  display: flex;
  flex-wrap: nowrap;
  gap: 4px;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
  scrollbar-color: $color-border-default transparent;
  padding-bottom: 2px;

  &::-webkit-scrollbar {
    height: 4px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  &::-webkit-scrollbar-thumb {
    background: $color-border-default;
    border-radius: $radius-pill;
  }
}
</style>
