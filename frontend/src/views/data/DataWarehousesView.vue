<template>
  <PageSectionCard title="仓库数据" description="展示外部仓库基础数据和手工维护的国家映射。">
    <el-table v-loading="loading" :data="pagedRows">
      <el-table-column label="仓库 ID" prop="id" width="120" />
      <el-table-column label="仓库名称" prop="name" min-width="240" />
      <el-table-column label="仓库类型" width="120" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.type === 1" type="success" size="small">国内仓</el-tag>
          <el-tag v-else-if="row.type === 0" size="small">默认仓</el-tag>
          <el-tag v-else-if="row.type === 2" size="small">FBA 仓</el-tag>
          <el-tag v-else-if="row.type === 3" size="small">海外仓</el-tag>
          <el-tag v-else-if="row.type === -1" type="info" size="small">虚拟仓</el-tag>
          <el-tag v-else type="info" size="small">{{ row.type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="所属国家" width="160">
        <template #default="{ row }">
          <el-tag v-if="row.country" size="small">{{ row.country }}</el-tag>
          <el-tag v-else type="warning" size="small">待指定</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="补货站点" prop="replenishSite" width="180">
        <template #default="{ row }">
          <span class="muted mono">{{ row.replenishSite || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="最近同步时间" width="160">
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
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import dayjs from 'dayjs'
import { computed, onMounted, ref } from 'vue'

const rows = ref<DataWarehouse[]>([])
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
    const resp = await listDataWarehouses()
    rows.value = resp.items
  } finally {
    loading.value = false
  }
}

function formatTime(value: string): string {
  return dayjs(value).format('MM-DD HH:mm')
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
</style>
