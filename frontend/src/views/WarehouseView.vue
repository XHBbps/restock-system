<template>
  <PageSectionCard title="仓库配置">
    <template #actions>
      <el-tag type="info" size="small">类型 1 表示国内仓</el-tag>
    </template>

    <el-table v-loading="loading" :data="pagedRows">
      <el-table-column label="仓库名称" prop="name" min-width="220" sortable>
        <template #default="{ row }">
          {{ row.name }}
          <el-tag v-if="!row.country" type="warning" size="small" style="margin-left: 8px">
            待指定国家
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="仓库 ID" prop="id" width="140" sortable show-overflow-tooltip />
      <el-table-column label="类型" prop="type" width="100" align="center" sortable show-overflow-tooltip />
      <el-table-column label="replenishSite" width="180" sortable>
        <template #default="{ row }">
          <span class="hint">{{ row.replenish_site_raw || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="所属国家" width="220">
        <template #default="{ row }">
          <el-select
            v-model="row.country"
            filterable
            placeholder="选择国家"
            style="width: 180px"
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
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

const rows = ref<Warehouse[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)

const countryOptions = [
  { code: 'US', label: 'US - 美国' },
  { code: 'CA', label: 'CA - 加拿大' },
  { code: 'MX', label: 'MX - 墨西哥' },
  { code: 'GB', label: 'GB - 英国' },
  { code: 'DE', label: 'DE - 德国' },
  { code: 'FR', label: 'FR - 法国' },
  { code: 'IT', label: 'IT - 意大利' },
  { code: 'ES', label: 'ES - 西班牙' },
  { code: 'IN', label: 'IN - 印度' },
  { code: 'JP', label: 'JP - 日本' },
  { code: 'AU', label: 'AU - 澳大利亚' },
  { code: 'AE', label: 'AE - 阿联酋' },
  { code: 'TR', label: 'TR - 土耳其' },
  { code: 'SG', label: 'SG - 新加坡' },
  { code: 'BR', label: 'BR - 巴西' },
  { code: 'NL', label: 'NL - 荷兰' },
  { code: 'SA', label: 'SA - 沙特阿拉伯' },
  { code: 'SE', label: 'SE - 瑞典' },
  { code: 'PL', label: 'PL - 波兰' },
  { code: 'BE', label: 'BE - 比利时' },
  { code: 'IE', label: 'IE - 爱尔兰' },
]

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
