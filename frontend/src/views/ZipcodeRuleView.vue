<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <span class="card-title">邮编规则</span>
        <div class="actions">
          <el-input
            v-model="filterCountry"
            placeholder="按国家筛选"
            clearable
            style="width: 160px"
            maxlength="2"
            @clear="reload"
            @keyup.enter="reload"
          />
          <el-button type="primary" @click="openCreate">新增规则</el-button>
        </div>
      </div>
    </template>

    <el-table :data="rows" v-loading="loading">
      <el-table-column label="优先级" prop="priority" width="80" sortable />
      <el-table-column label="国家" prop="country" width="80" />
      <el-table-column label="截取前 N 位" prop="prefix_length" width="120" />
      <el-table-column label="值类型" prop="value_type" width="100" />
      <el-table-column label="比较" width="80">
        <template #default="{ row }">
          <code>{{ row.operator }}</code>
        </template>
      </el-table-column>
      <el-table-column label="比较值" prop="compare_value" width="120" />
      <el-table-column label="目标仓库" prop="warehouse_id" min-width="160">
        <template #default="{ row }">
          {{ warehouseName(row.warehouse_id) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑规则' : '新增规则'" width="540px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="国家代码">
          <el-input v-model="form.country" maxlength="2" style="width: 120px" />
        </el-form-item>
        <el-form-item label="截取前 N 位">
          <el-input-number v-model="form.prefix_length" :min="1" :max="10" />
        </el-form-item>
        <el-form-item label="值类型">
          <el-radio-group v-model="form.value_type">
            <el-radio-button value="number">数值</el-radio-button>
            <el-radio-button value="string">字符串</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="比较操作符">
          <el-select v-model="form.operator" style="width: 160px">
            <el-option v-for="op in OPERATORS" :key="op" :label="op" :value="op" />
          </el-select>
        </el-form-item>
        <el-form-item label="比较值">
          <el-input v-model="form.compare_value" style="width: 220px" />
        </el-form-item>
        <el-form-item label="目标仓库">
          <el-select v-model="form.warehouse_id" filterable style="width: 280px">
            <el-option
              v-for="w in warehouses"
              :key="w.id"
              :label="`${w.name} (${w.country || '?'})`"
              :value="w.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="1" />
          <span class="hint">数字越小越先匹配</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import {
  createZipcodeRule,
  deleteZipcodeRule,
  listWarehouses,
  listZipcodeRules,
  updateZipcodeRule,
  type Warehouse,
  type ZipcodeRule,
  type ZipcodeRuleInput
} from '@/api/config'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

const OPERATORS = ['=', '!=', '>', '>=', '<', '<='] as const

const rows = ref<ZipcodeRule[]>([])
const warehouses = ref<Warehouse[]>([])
const loading = ref(false)
const saving = ref(false)
const filterCountry = ref('')

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)

const form = reactive<ZipcodeRuleInput>({
  country: '',
  prefix_length: 2,
  value_type: 'number',
  operator: '>=',
  compare_value: '',
  warehouse_id: '',
  priority: 100
})

async function reload(): Promise<void> {
  loading.value = true
  try {
    rows.value = await listZipcodeRules(filterCountry.value || undefined)
  } finally {
    loading.value = false
  }
}

function warehouseName(id: string): string {
  const w = warehouses.value.find((x) => x.id === id)
  return w ? `${w.name} (${w.country || '?'})` : id
}

function openCreate(): void {
  editingId.value = null
  Object.assign(form, {
    country: '',
    prefix_length: 2,
    value_type: 'number',
    operator: '>=',
    compare_value: '',
    warehouse_id: '',
    priority: 100
  })
  dialogVisible.value = true
}

function openEdit(row: ZipcodeRule): void {
  editingId.value = row.id
  Object.assign(form, { ...row })
  dialogVisible.value = true
}

async function save(): Promise<void> {
  saving.value = true
  try {
    if (editingId.value) {
      await updateZipcodeRule(editingId.value, { ...form })
    } else {
      await createZipcodeRule({ ...form })
    }
    dialogVisible.value = false
    ElMessage.success('已保存')
    await reload()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function remove(row: ZipcodeRule): Promise<void> {
  await ElMessageBox.confirm(`确认删除规则 #${row.id}?`, '删除', { type: 'warning' })
  try {
    await deleteZipcodeRule(row.id)
    ElMessage.success('已删除')
    await reload()
  } catch {
    ElMessage.error('删除失败')
  }
}

onMounted(async () => {
  warehouses.value = await listWarehouses()
  await reload()
})
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
.actions {
  display: flex;
  gap: $space-3;
}
.hint {
  margin-left: $space-3;
  color: $color-text-secondary;
  font-size: $font-size-xs;
}
</style>
