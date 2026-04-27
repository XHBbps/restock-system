<template>
  <PageSectionCard
    title="映射规则"
    description="维护商品 SKU 与库存包裹 SKU 的组装关系，补货计算会按同仓库组件数量换算。"
  >
    <template #actions>
      <el-input
        v-model="keyword"
        clearable
        placeholder="搜索商品SKU / 库存SKU"
        style="width: 220px"
        @keyup.enter="reloadFromFirstPage"
        @clear="reloadFromFirstPage"
      />
      <el-select
        v-model="enabledFilter"
        clearable
        placeholder="启用状态"
        style="width: 132px"
        @change="reloadFromFirstPage"
      >
        <el-option label="启用" :value="true" />
        <el-option label="停用" :value="false" />
      </el-select>
      <el-button @click="reloadFromFirstPage">搜索</el-button>
      <el-button @click="handleExport">导出</el-button>
      <el-button v-if="canEdit" @click="triggerImport">导入</el-button>
      <el-button v-if="canEdit" type="primary" @click="openCreate">新增规则</el-button>
      <input
        ref="fileInput"
        class="file-input"
        type="file"
        accept=".xlsx,.csv"
        @change="handleImportFile"
      >
    </template>

    <el-table v-loading="loading" :data="rows" row-key="id" empty-text="暂无映射规则">
      <el-table-column label="商品 SKU" prop="commodity_sku" min-width="180" show-overflow-tooltip />
      <el-table-column label="公式预览" prop="formula_preview" min-width="260" show-overflow-tooltip />
      <el-table-column label="组件数量" prop="component_count" width="100" align="center" />
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'">
            {{ row.enabled ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="备注" prop="remark" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ row.remark || '-' }}</template>
      </el-table-column>
      <el-table-column label="更新时间" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ formatShortTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column v-if="canEdit" label="操作" width="190" align="center" fixed="right">
        <template #default="{ row }">
          <div class="row-actions">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="toggleEnabled(row)">
              {{ row.enabled ? '停用' : '启用' }}
            </el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <TablePaginationBar
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
    />

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑映射规则' : '新增映射规则'"
      width="720px"
      destroy-on-close
      @closed="resetDialog"
    >
      <el-form label-width="108px" class="mapping-form">
        <el-form-item label="商品SKU">
          <el-input v-model="form.commodity_sku" placeholder="例如 A-SKU" class="form-field" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item label="组件">
          <div class="component-editor">
            <div
              v-for="(component, index) in form.components"
              :key="index"
              class="component-row"
            >
              <el-input
                v-model="component.inventory_sku"
                placeholder="库存SKU"
                class="component-row__sku"
              />
              <el-input-number
                v-model="component.quantity"
                :min="1"
                :step="1"
                step-strictly
                class="component-row__qty"
              />
              <el-button
                :disabled="form.components.length === 1"
                link
                type="danger"
                @click="removeComponent(index)"
              >
                删除
              </el-button>
            </div>
            <el-button text type="primary" @click="addComponent">添加组件</el-button>
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="form.remark"
            type="textarea"
            :rows="3"
            maxlength="1000"
            show-word-limit
            class="form-field"
          />
        </el-form-item>
        <el-form-item label="公式预览">
          <div class="formula-preview">{{ formulaPreview }}</div>
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
import {
  createSkuMappingRule,
  deleteSkuMappingRule,
  exportSkuMappingRules,
  importSkuMappingRules,
  listSkuMappingRules,
  updateSkuMappingRule,
  type SkuMappingRule,
  type SkuMappingRuleInput,
} from '@/api/config'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { useAuthStore } from '@/stores/auth'
import { getActionErrorMessage } from '@/utils/apiError'
import { triggerBlobDownload } from '@/utils/download'
import { formatShortTime } from '@/utils/format'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'

const auth = useAuthStore()
const canEdit = computed(() => auth.hasPermission('config:edit'))

const rows = ref<SkuMappingRule[]>([])
const total = ref(0)
const loading = ref(false)
const saving = ref(false)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const enabledFilter = ref<boolean | ''>('')
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const form = reactive<SkuMappingRuleInput>({
  commodity_sku: '',
  enabled: true,
  remark: '',
  components: [{ inventory_sku: '', quantity: 1 }],
})

const formulaPreview = computed(() => {
  const sku = form.commodity_sku.trim() || '商品SKU'
  const parts = form.components
    .filter((component) => component.inventory_sku.trim())
    .map((component) => `${component.quantity || 1}*${component.inventory_sku.trim()}`)
  return `${sku}=${parts.length ? parts.join('+') : '库存SKU组件'}`
})

async function reload(): Promise<void> {
  loading.value = true
  try {
    const result = await listSkuMappingRules({
      keyword: keyword.value.trim() || undefined,
      enabled: enabledFilter.value === '' ? undefined : enabledFilter.value,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = result.items
    total.value = result.total
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '加载映射规则失败'))
  } finally {
    loading.value = false
  }
}

function reloadFromFirstPage(): void {
  page.value = 1
  void reload()
}

function resetForm(): void {
  Object.assign(form, {
    commodity_sku: '',
    enabled: true,
    remark: '',
    components: [{ inventory_sku: '', quantity: 1 }],
  })
}

function openCreate(): void {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: SkuMappingRule): void {
  editingId.value = row.id
  Object.assign(form, {
    commodity_sku: row.commodity_sku,
    enabled: row.enabled,
    remark: row.remark || '',
    components: row.components.map((component) => ({
      inventory_sku: component.inventory_sku,
      quantity: component.quantity,
    })),
  })
  dialogVisible.value = true
}

function resetDialog(): void {
  editingId.value = null
  resetForm()
}

function addComponent(): void {
  form.components.push({ inventory_sku: '', quantity: 1 })
}

function removeComponent(index: number): void {
  if (form.components.length <= 1) return
  form.components.splice(index, 1)
}

function buildPayload(): SkuMappingRuleInput | null {
  const commoditySku = form.commodity_sku.trim()
  if (!commoditySku) {
    ElMessage.warning('请输入商品SKU')
    return null
  }
  const components = form.components.map((component) => ({
    inventory_sku: component.inventory_sku.trim(),
    quantity: Number(component.quantity),
  }))
  if (components.some((component) => !component.inventory_sku)) {
    ElMessage.warning('请输入库存SKU')
    return null
  }
  if (components.some((component) => !Number.isInteger(component.quantity) || component.quantity <= 0)) {
    ElMessage.warning('组件数量必须为正整数')
    return null
  }
  const uniqueSkus = new Set(components.map((component) => component.inventory_sku))
  if (uniqueSkus.size !== components.length) {
    ElMessage.warning('同一规则内库存SKU不能重复')
    return null
  }
  return {
    commodity_sku: commoditySku,
    enabled: form.enabled,
    remark: form.remark?.trim() || null,
    components,
  }
}

async function save(): Promise<void> {
  const payload = buildPayload()
  if (!payload) return

  saving.value = true
  try {
    if (editingId.value) {
      await updateSkuMappingRule(editingId.value, payload)
    } else {
      await createSkuMappingRule(payload)
    }
    dialogVisible.value = false
    ElMessage.success('已保存')
    await reload()
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '保存映射规则失败'))
  } finally {
    saving.value = false
  }
}

async function toggleEnabled(row: SkuMappingRule): Promise<void> {
  try {
    await updateSkuMappingRule(row.id, { enabled: !row.enabled })
    ElMessage.success(row.enabled ? '已停用' : '已启用')
    await reload()
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '更新状态失败'))
  }
}

async function remove(row: SkuMappingRule): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除商品SKU ${row.commodity_sku} 的映射规则吗？`, '删除规则', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteSkuMappingRule(row.id)
    ElMessage.success('已删除')
    await reload()
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '删除映射规则失败'))
  }
}

async function handleExport(): Promise<void> {
  try {
    const blob = await exportSkuMappingRules()
    triggerBlobDownload(blob, `sku_mapping_rules_${Date.now()}.xlsx`)
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '导出映射规则失败'))
  }
}

function triggerImport(): void {
  fileInput.value?.click()
}

async function handleImportFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  try {
    const result = await importSkuMappingRules(file)
    ElMessage.success(
      `导入完成：新增 ${result.created} 条，更新 ${result.updated} 条，组件 ${result.total_components} 行`,
    )
    await reload()
  } catch (error) {
    ElMessage.error(formatImportError(error))
  }
}

function formatImportError(error: unknown): string {
  const response = (error as {
    response?: { data?: { detail?: { errors?: Array<{ row?: number | null; message?: string }> } } }
  }).response
  const errors = response?.data?.detail?.errors
  if (errors?.length) {
    const first = errors[0]
    const rowText = first.row ? `第 ${first.row} 行：` : ''
    return `${rowText}${first.message || '导入校验失败'}`
  }
  return getActionErrorMessage(error, '导入映射规则失败')
}

watch([page, pageSize], () => {
  void reload()
})

onMounted(() => {
  void reload()
})
</script>

<style scoped lang="scss">
.row-actions {
  display: inline-flex;
  align-items: center;
  gap: $space-2;
}

.file-input {
  display: none;
}

.mapping-form {
  :deep(.el-form-item__label) {
    color: $color-text-secondary;
    font-size: $font-size-sm;
    font-weight: $font-weight-medium;
  }
}

.form-field {
  width: 420px;
}

.component-editor {
  display: flex;
  flex-direction: column;
  gap: $space-2;
  width: 100%;
}

.component-row {
  display: flex;
  align-items: center;
  gap: $space-2;
}

.component-row__sku {
  width: 300px;
}

.component-row__qty {
  width: 132px;
}

.formula-preview {
  min-height: 36px;
  padding: 7px $space-3;
  border: 1px solid $color-border-default;
  border-radius: $radius-md;
  background: $color-bg-subtle;
  color: $color-text-primary;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: $font-size-sm;
  line-height: $line-height-normal;
  word-break: break-word;
}

@media (max-width: 820px) {
  .form-field,
  .component-row__sku {
    width: 100%;
  }

  .component-row {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
