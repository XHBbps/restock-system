<template>
  <PageSectionCard
    title="仓库配置"
    description="维护仓库与国家映射。页面级表格统一支持分页。"
  >
    <template #actions>
      <el-tag type="info" size="small">类型 1 表示国内仓</el-tag>
    </template>

    <el-table v-loading="loading" :data="pagedRows">
      <el-table-column label="仓库名称" prop="name" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.name }}
          <el-tag v-if="!row.country" type="warning" size="small" style="margin-left: 8px">
            待指定国家
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="仓库 ID" prop="id" width="140" show-overflow-tooltip />
      <el-table-column label="类型" prop="type" width="100" align="center" show-overflow-tooltip />
      <el-table-column label="赛狐 replenishSite" width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="hint">{{ row.replenish_site_raw || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="所属国家" width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <el-input
            v-model="row.country"
            placeholder="ISO 两位码"
            maxlength="2"
            style="width: 140px"
            @blur="(e: Event) => save(row, (e.target as HTMLInputElement).value)"
            @keyup.enter="(e: Event) => save(row, (e.target as HTMLInputElement).value)"
          />
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
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

const rows = ref<Warehouse[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return rows.value.slice(start, start + pageSize.value)
})

async function reload(): Promise<void> {
  loading.value = true
  try {
    rows.value = await listWarehouses()
  } finally {
    loading.value = false
  }
}

async function save(row: Warehouse, value: string): Promise<void> {
  const nextCountry = value.trim().toUpperCase()
  if (!nextCountry || nextCountry.length !== 2) {
    ElMessage.warning('请输入 2 位国家代码。')
    return
  }
  if (nextCountry === row.country) return
  try {
    await patchWarehouseCountry(row.id, nextCountry)
    row.country = nextCountry
    ElMessage.success(`${row.name} 已更新为 ${nextCountry}。`)
  } catch {
    ElMessage.error('更新失败。')
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
