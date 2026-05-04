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
      <el-table-column label="同物组" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ physicalGroupLabel(row.commodity_sku) }}</template>
      </el-table-column>
      <el-table-column label="组件同物组" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ componentPhysicalGroupLabels(row) }}</template>
      </el-table-column>
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
            <section
              v-for="group in formGroups"
              :key="group.groupNo"
              class="component-group"
            >
              <div class="component-group__header">
                <span>方案 {{ group.groupNo }}</span>
                <el-button link type="primary" @click="addComponent(group.groupNo)">添加组件</el-button>
              </div>
              <div
                v-for="{ component, index } in group.components"
                :key="index"
                class="component-row"
              >
                <el-input-number
                  v-model="component.group_no"
                  :min="1"
                  :step="1"
                  step-strictly
                  class="component-row__group"
                />
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
                  class="component-delete-button"
                  :disabled="form.components.length === 1"
                  link
                  type="danger"
                  @click="removeComponent(index)"
                >
                  删除
                </el-button>
              </div>
            </section>
            <el-button class="component-add-button" @click="addGroup">添加方案</el-button>
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

  <PageSectionCard
    title="同物共享组"
    description="维护完全等价的商品 SKU / 库存 SKU，共享组内 SKU 在补货计算前统一归一到主 SKU。"
    class="physical-section"
  >
    <template #actions>
      <el-input
        v-model="physicalKeyword"
        clearable
        placeholder="搜索组名 / SKU"
        style="width: 220px"
        @keyup.enter="reloadPhysicalFromFirstPage"
        @clear="reloadPhysicalFromFirstPage"
      />
      <el-select
        v-model="physicalEnabledFilter"
        clearable
        placeholder="启用状态"
        style="width: 132px"
        @change="reloadPhysicalFromFirstPage"
      >
        <el-option label="启用" :value="true" />
        <el-option label="停用" :value="false" />
      </el-select>
      <el-button @click="reloadPhysicalFromFirstPage">搜索</el-button>
      <el-button v-if="canEdit" type="primary" @click="openPhysicalCreate">新增共享组</el-button>
    </template>

    <el-table
      v-loading="physicalLoading"
      :data="physicalGroups"
      row-key="id"
      empty-text="暂无同物共享组"
    >
      <el-table-column label="组名" prop="name" min-width="160" show-overflow-tooltip />
      <el-table-column label="主 SKU" prop="primary_sku" min-width="160" show-overflow-tooltip />
      <el-table-column label="别名 SKU" min-width="260" show-overflow-tooltip>
        <template #default="{ row }">{{ aliasText(row) }}</template>
      </el-table-column>
      <el-table-column label="成员数" prop="alias_count" width="90" align="center" />
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
      <el-table-column v-if="canEdit" label="操作" width="190" align="center" fixed="right">
        <template #default="{ row }">
          <div class="row-actions">
            <el-button link type="primary" @click="openPhysicalEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="togglePhysicalEnabled(row)">
              {{ row.enabled ? '停用' : '启用' }}
            </el-button>
            <el-button link type="danger" @click="removePhysical(row)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <TablePaginationBar
      v-model:current-page="physicalPage"
      v-model:page-size="physicalPageSize"
      :total="physicalTotal"
    />

    <el-dialog
      v-model="physicalDialogVisible"
      :title="editingPhysicalId ? '编辑同物共享组' : '新增同物共享组'"
      width="640px"
      destroy-on-close
      @closed="resetPhysicalDialog"
    >
      <el-form label-width="108px" class="mapping-form">
        <el-form-item label="组名">
          <el-input v-model="physicalForm.name" placeholder="例如 A 款同物" class="form-field" />
        </el-form-item>
        <el-form-item label="主 SKU">
          <el-input v-model="physicalForm.primary_sku" placeholder="用于建议单与导出的 SKU" class="form-field" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="physicalForm.enabled" />
        </el-form-item>
        <el-form-item label="别名 SKU">
          <div class="alias-editor">
            <div v-for="(_, index) in physicalForm.aliases" :key="index" class="alias-row">
              <el-input v-model="physicalForm.aliases[index]" placeholder="商品 SKU 或库存 SKU" />
              <el-button
                link
                type="danger"
                :disabled="physicalForm.aliases.length === 1"
                @click="removeAlias(index)"
              >
                删除
              </el-button>
            </div>
            <el-button class="component-add-button" @click="addAlias">添加别名</el-button>
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="physicalForm.remark"
            type="textarea"
            :rows="3"
            maxlength="1000"
            show-word-limit
            class="form-field"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="physicalDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="physicalSaving" @click="savePhysical">保存</el-button>
      </template>
    </el-dialog>
  </PageSectionCard>
</template>

<script setup lang="ts">
import {
  createPhysicalItemGroup,
  createSkuMappingRule,
  deletePhysicalItemGroup,
  deleteSkuMappingRule,
  exportSkuMappingRules,
  importSkuMappingRules,
  listPhysicalItemGroups,
  listSkuMappingRules,
  updatePhysicalItemGroup,
  type PhysicalItemGroup,
  type PhysicalItemGroupInput,
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
const physicalGroups = ref<PhysicalItemGroup[]>([])
const physicalTotal = ref(0)
const loading = ref(false)
const physicalLoading = ref(false)
const saving = ref(false)
const physicalSaving = ref(false)
const page = ref(1)
const pageSize = ref(20)
const physicalPage = ref(1)
const physicalPageSize = ref(20)
const keyword = ref('')
const physicalKeyword = ref('')
const enabledFilter = ref<boolean | ''>('')
const physicalEnabledFilter = ref<boolean | ''>('')
const dialogVisible = ref(false)
const physicalDialogVisible = ref(false)
const editingId = ref<number | null>(null)
const editingPhysicalId = ref<number | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const form = reactive<SkuMappingRuleInput>({
  commodity_sku: '',
  enabled: true,
  remark: '',
  components: [{ group_no: 1, inventory_sku: '', quantity: 1 }],
})

const physicalForm = reactive<PhysicalItemGroupInput>({
  name: '',
  primary_sku: '',
  enabled: true,
  remark: '',
  aliases: [''],
})

const formGroups = computed(() => {
  const groups = new Map<number, Array<{ component: SkuMappingRuleInput['components'][number]; index: number }>>()
  form.components.forEach((component, index) => {
    const groupNo = Number(component.group_no) || 1
    const rows = groups.get(groupNo) ?? []
    rows.push({ component, index })
    groups.set(groupNo, rows)
  })
  return Array.from(groups.entries())
    .sort(([left], [right]) => left - right)
    .map(([groupNo, components]) => ({ groupNo, components }))
})

const formulaPreview = computed(() => {
  const sku = form.commodity_sku.trim() || '商品SKU'
  const groups = formGroups.value
    .map((group) =>
      group.components
        .map(({ component }) => component)
        .filter((component) => component.inventory_sku.trim())
        .map((component) => `${component.quantity || 1}*${component.inventory_sku.trim()}`)
        .join('+'),
    )
    .filter(Boolean)
  return `${sku}=${groups.length ? groups.join(' 或 ') : '库存SKU组件'}`
})

const physicalSkuIndex = computed(() => {
  const index = new Map<string, PhysicalItemGroup>()
  physicalGroups.value.forEach((group) => {
    group.aliases.forEach((alias) => index.set(alias.sku, group))
  })
  return index
})

function physicalGroupLabel(sku: string): string {
  const group = physicalSkuIndex.value.get(sku)
  if (!group) return '-'
  return `${group.name}（主 ${group.primary_sku}）`
}

function componentPhysicalGroupLabels(row: SkuMappingRule): string {
  const labels = row.components
    .map((component) => physicalSkuIndex.value.get(component.inventory_sku)?.name)
    .filter((value): value is string => Boolean(value))
  return Array.from(new Set(labels)).join('、') || '-'
}

function aliasText(row: PhysicalItemGroup): string {
  return row.aliases.map((alias) => alias.sku).join('、')
}

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

async function reloadPhysical(): Promise<void> {
  physicalLoading.value = true
  try {
    const result = await listPhysicalItemGroups({
      keyword: physicalKeyword.value.trim() || undefined,
      enabled: physicalEnabledFilter.value === '' ? undefined : physicalEnabledFilter.value,
      page: physicalPage.value,
      page_size: physicalPageSize.value,
    })
    physicalGroups.value = result.items
    physicalTotal.value = result.total
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '加载同物共享组失败'))
  } finally {
    physicalLoading.value = false
  }
}

function reloadFromFirstPage(): void {
  page.value = 1
  void reload()
}

function reloadPhysicalFromFirstPage(): void {
  physicalPage.value = 1
  void reloadPhysical()
}

function resetForm(): void {
  Object.assign(form, {
    commodity_sku: '',
    enabled: true,
    remark: '',
    components: [{ group_no: 1, inventory_sku: '', quantity: 1 }],
  })
}

function resetPhysicalForm(): void {
  Object.assign(physicalForm, {
    name: '',
    primary_sku: '',
    enabled: true,
    remark: '',
    aliases: [''],
  })
}

function openCreate(): void {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openPhysicalCreate(): void {
  editingPhysicalId.value = null
  resetPhysicalForm()
  physicalDialogVisible.value = true
}

function openEdit(row: SkuMappingRule): void {
  editingId.value = row.id
  Object.assign(form, {
    commodity_sku: row.commodity_sku,
    enabled: row.enabled,
    remark: row.remark || '',
    components: row.components.map((component) => ({
      group_no: component.group_no,
      inventory_sku: component.inventory_sku,
      quantity: component.quantity,
    })),
  })
  dialogVisible.value = true
}

function openPhysicalEdit(row: PhysicalItemGroup): void {
  editingPhysicalId.value = row.id
  Object.assign(physicalForm, {
    name: row.name,
    primary_sku: row.primary_sku,
    enabled: row.enabled,
    remark: row.remark || '',
    aliases: row.aliases.map((alias) => alias.sku),
  })
  physicalDialogVisible.value = true
}

function resetDialog(): void {
  editingId.value = null
  resetForm()
}

function resetPhysicalDialog(): void {
  editingPhysicalId.value = null
  resetPhysicalForm()
}

function addComponent(groupNo = 1): void {
  form.components.push({ group_no: groupNo, inventory_sku: '', quantity: 1 })
}

function addGroup(): void {
  const nextGroupNo = Math.max(0, ...form.components.map((component) => Number(component.group_no) || 0)) + 1
  addComponent(nextGroupNo)
}

function removeComponent(index: number): void {
  if (form.components.length <= 1) return
  form.components.splice(index, 1)
}

function addAlias(): void {
  physicalForm.aliases.push('')
}

function removeAlias(index: number): void {
  if (physicalForm.aliases.length <= 1) return
  physicalForm.aliases.splice(index, 1)
}

function buildPayload(): SkuMappingRuleInput | null {
  const commoditySku = form.commodity_sku.trim()
  if (!commoditySku) {
    ElMessage.warning('请输入商品SKU')
    return null
  }
  const components = form.components.map((component) => ({
    group_no: Number(component.group_no),
    inventory_sku: component.inventory_sku.trim(),
    quantity: Number(component.quantity),
  }))
  if (components.some((component) => !component.inventory_sku)) {
    ElMessage.warning('请输入库存SKU')
    return null
  }
  if (components.some((component) => !Number.isInteger(component.group_no) || component.group_no <= 0)) {
    ElMessage.warning('组合编号必须为正整数')
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
    components: components.sort((left, right) => left.group_no - right.group_no),
  }
}

function buildPhysicalPayload(): PhysicalItemGroupInput | null {
  const name = physicalForm.name.trim()
  const primarySku = physicalForm.primary_sku.trim()
  const aliases = physicalForm.aliases.map((sku) => sku.trim()).filter(Boolean)
  if (!name) {
    ElMessage.warning('请输入共享组名称')
    return null
  }
  if (!primarySku) {
    ElMessage.warning('请输入主 SKU')
    return null
  }
  if (!aliases.length) {
    ElMessage.warning('请至少输入一个别名 SKU')
    return null
  }
  if (!aliases.includes(primarySku)) {
    ElMessage.warning('主 SKU 必须属于别名成员')
    return null
  }
  if (new Set(aliases).size !== aliases.length) {
    ElMessage.warning('别名 SKU 不能重复')
    return null
  }
  return {
    name,
    primary_sku: primarySku,
    enabled: physicalForm.enabled,
    remark: physicalForm.remark?.trim() || null,
    aliases,
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

async function savePhysical(): Promise<void> {
  const payload = buildPhysicalPayload()
  if (!payload) return

  physicalSaving.value = true
  try {
    if (editingPhysicalId.value) {
      await updatePhysicalItemGroup(editingPhysicalId.value, payload)
    } else {
      await createPhysicalItemGroup(payload)
    }
    physicalDialogVisible.value = false
    ElMessage.success('已保存')
    await reloadPhysical()
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '保存同物共享组失败'))
  } finally {
    physicalSaving.value = false
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

async function togglePhysicalEnabled(row: PhysicalItemGroup): Promise<void> {
  try {
    await updatePhysicalItemGroup(row.id, { enabled: !row.enabled })
    ElMessage.success(row.enabled ? '已停用' : '已启用')
    await reloadPhysical()
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '更新同物共享组状态失败'))
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

async function removePhysical(row: PhysicalItemGroup): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除同物共享组 ${row.name} 吗？`, '删除共享组', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deletePhysicalItemGroup(row.id)
    ElMessage.success('已删除')
    await reloadPhysical()
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '删除同物共享组失败'))
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

watch([physicalPage, physicalPageSize], () => {
  void reloadPhysical()
})

onMounted(() => {
  void reload()
  void reloadPhysical()
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

.physical-section {
  margin-top: $space-5;
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

.component-group {
  display: flex;
  flex-direction: column;
  gap: $space-2;
  padding: $space-3;
  border: 1px solid $color-border-default;
  border-radius: $radius-md;
  background: $color-bg-subtle;
}

.component-group__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: $color-text-secondary;
  font-size: $font-size-sm;
  font-weight: $font-weight-medium;
}

.component-row {
  display: flex;
  align-items: center;
  gap: $space-2;
}

.alias-editor {
  display: flex;
  flex-direction: column;
  gap: $space-2;
  width: 420px;
}

.alias-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: $space-2;
  align-items: center;
}

.component-row__group {
  width: 96px;
}

.component-row__sku {
  width: 260px;
}

.component-row__qty {
  width: 132px;
}

.component-add-button.el-button {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  box-sizing: border-box;
  width: 420px;
  height: 32px;
  min-width: max-content;
  padding: 0 12px;
  border: 1px solid $color-border-default;
  border-radius: $radius-md;
  background: $color-bg-card;
  color: $color-text-primary;
  font-weight: $font-weight-medium;
  white-space: nowrap;
  transition: $transition-fast;

  :deep(span) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    line-height: 1;
    white-space: nowrap;
  }

  &:hover:not(.is-disabled),
  &:focus:not(.is-disabled) {
    border-color: $color-border-strong;
    background: $color-bg-subtle;
    color: $color-text-primary;
  }
}

.component-delete-button.el-button.is-link.el-button--danger {
  color: $color-danger;
  transition:
    color $transition-fast,
    background-color $transition-fast;

  &:hover:not(.is-disabled),
  &:focus:not(.is-disabled) {
    background: $color-danger-soft;
    color: $color-danger-dark;
  }

  &.is-disabled {
    color: $color-text-disabled;
  }
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

  .component-row__group,
  .component-row__qty {
    width: 100%;
  }

  .component-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .alias-editor {
    width: 100%;
  }

  .alias-row {
    grid-template-columns: 1fr;
  }

  .component-add-button.el-button {
    width: 100%;
    min-width: 0;
  }
}
</style>
