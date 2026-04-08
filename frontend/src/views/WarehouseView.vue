<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <span class="card-title">仓库与国家映射</span>
        <div class="legend">
          <el-tag type="info" size="small">类型 1 = 国内仓 (本地仓)</el-tag>
        </div>
      </div>
    </template>

    <el-table :data="rows" v-loading="loading">
      <el-table-column label="名称" prop="name" min-width="200">
        <template #default="{ row }">
          {{ row.name }}
          <el-tag v-if="!row.country" type="warning" size="small" style="margin-left: 8px">
            待指定国家
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="ID" prop="id" width="120" />
      <el-table-column label="类型" prop="type" width="100" />
      <el-table-column label="赛狐 replenishSite" width="160">
        <template #default="{ row }">
          <span class="hint">{{ row.replenish_site_raw || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="所属国家" width="200">
        <template #default="{ row }">
          <el-input
            v-model="row.country"
            placeholder="ISO 二字码 (JP/US/...)"
            maxlength="2"
            style="width: 140px"
            @blur="(e: Event) => save(row, (e.target as HTMLInputElement).value)"
            @keyup.enter="(e: Event) => save(row, (e.target as HTMLInputElement).value)"
          />
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { listWarehouses, patchWarehouseCountry, type Warehouse } from '@/api/config'
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

const rows = ref<Warehouse[]>([])
const loading = ref(false)

async function reload(): Promise<void> {
  loading.value = true
  try {
    rows.value = await listWarehouses()
  } finally {
    loading.value = false
  }
}

async function save(row: Warehouse, value: string): Promise<void> {
  const v = value.trim().toUpperCase()
  if (!v || v.length !== 2) {
    ElMessage.warning('请输入 2 位国家代码')
    return
  }
  if (v === row.country) return
  try {
    await patchWarehouseCountry(row.id, v)
    row.country = v
    ElMessage.success(`${row.name} → ${v}`)
  } catch {
    ElMessage.error('更新失败')
  }
}

onMounted(reload)
</script>

<style lang="scss" scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}
.hint {
  color: $color-text-secondary;
  font-size: $font-size-xs;
}
</style>
