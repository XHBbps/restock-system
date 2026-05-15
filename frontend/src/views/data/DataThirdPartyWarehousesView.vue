<template>
  <PageSectionCard title="海外仓">
    <template #actions>
      <el-input v-model="filters.keyword" placeholder="搜索海外仓名" clearable style="width: 180px" @keyup.enter="reload(true)" />
      <el-select v-model="filters.country" placeholder="国家" clearable filterable style="width: 140px" @change="reload(true)">
        <el-option v-for="option in countryOptions" :key="option.code" :label="option.label" :value="option.code" />
      </el-select>
      <el-checkbox v-model="filters.only_missing_country" @change="reload(true)">仅看未维护国家</el-checkbox>
      <el-button v-if="auth.hasPermission('data_base:edit')" type="primary" @click="openCreate">新增海外仓</el-button>
    </template>

    <el-table v-loading="loading" :data="rows" row-key="id" empty-text="暂无海外仓">
      <el-table-column label="海外仓" prop="name" min-width="220" show-overflow-tooltip />
      <el-table-column label="国家" width="180">
        <template #default="{ row }">
          <el-tag v-if="row.country" size="small">{{ row.country }}</el-tag>
          <el-tag v-else size="small" type="warning">未维护</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="SKU 数" prop="currentSkuCount" width="100" align="right" />
      <el-table-column label="可用合计" prop="currentTotalAvailable" width="120" align="right" />
      <el-table-column label="占用合计" prop="currentTotalReserved" width="120" align="right" />
      <el-table-column label="导入历史行" prop="importItemCount" width="120" align="right" />
      <el-table-column label="更新时间" width="168">
        <template #default="{ row }">
          <span class="muted mono">{{ formatUpdateTime(row.updatedAt) }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="auth.hasPermission('data_base:edit')" label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <TablePaginationBar
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100]"
      @current-change="reload(false)"
      @size-change="reload(true)"
    />

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑海外仓' : '新增海外仓'" width="420px">
      <el-form label-width="84px">
        <el-form-item label="海外仓名称" required>
          <el-input v-model="form.name" placeholder="请输入海外仓名称" />
        </el-form-item>
        <el-form-item label="所属国家">
          <el-select v-model="form.country" placeholder="未维护" clearable filterable style="width: 100%">
            <el-option v-for="option in countryOptions" :key="option.code" :label="option.label" :value="option.code" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </PageSectionCard>
</template>

<script setup lang="ts">
import { getCountryOptions, type CountryOption } from '@/api/config'
import {
  createThirdPartyWarehouse,
  deleteThirdPartyWarehouse,
  listThirdPartyWarehouses,
  updateThirdPartyWarehouse,
  type ThirdPartyWarehouse,
} from '@/api/data'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { useAuthStore } from '@/stores/auth'
import { getActionErrorMessage } from '@/utils/apiError'
import { COUNTRY_OPTIONS } from '@/utils/countries'
import { formatUpdateTime } from '@/utils/format'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

const auth = useAuthStore()
const rows = ref<ThirdPartyWarehouse[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editing = ref<ThirdPartyWarehouse | null>(null)
const filters = reactive({ keyword: '', country: '', only_missing_country: false })
const form = reactive({ name: '', country: '' })
const countryOptions = ref<CountryOption[]>(
  COUNTRY_OPTIONS.map((option) => ({ ...option, builtin: true, observed: false, can_be_eu_member: !['EU', 'ZZ'].includes(option.code) })),
)

async function reload(resetPage = false): Promise<void> {
  if (resetPage) page.value = 1
  loading.value = true
  try {
    const resp = await listThirdPartyWarehouses({
      keyword: filters.keyword || undefined,
      country: filters.country || undefined,
      only_missing_country: filters.only_missing_country,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = resp.items
    total.value = resp.total
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '加载海外仓失败'))
  } finally {
    loading.value = false
  }
}

async function loadCountryOptions(): Promise<void> {
  try {
    countryOptions.value = (await getCountryOptions()).items
  } catch {
    // keep builtin fallback
  }
}

function openCreate(): void {
  editing.value = null
  form.name = ''
  form.country = ''
  dialogVisible.value = true
}

function openEdit(row: ThirdPartyWarehouse): void {
  editing.value = row
  form.name = row.name
  form.country = row.country || ''
  dialogVisible.value = true
}

async function save(): Promise<void> {
  if (!form.name.trim()) {
    ElMessage.warning('请填写海外仓名称')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      await updateThirdPartyWarehouse(editing.value.id, { name: form.name, country: form.country || null })
      ElMessage.success('海外仓已更新')
    } else {
      await createThirdPartyWarehouse({ name: form.name, country: form.country || null })
      ElMessage.success('海外仓已创建')
    }
    dialogVisible.value = false
    await reload(false)
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '保存失败'))
  } finally {
    saving.value = false
  }
}

async function remove(row: ThirdPartyWarehouse): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除海外仓「${row.name}」？`, '删除确认', { type: 'warning' })
    await deleteThirdPartyWarehouse(row.id)
    ElMessage.success('海外仓已删除')
    await reload(false)
  } catch (err) {
    if (err !== 'cancel') ElMessage.error(getActionErrorMessage(err, '删除失败'))
  }
}

onMounted(() => {
  void loadCountryOptions()
  void reload()
})
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
