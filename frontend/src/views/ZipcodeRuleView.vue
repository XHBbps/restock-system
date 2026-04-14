<template>
  <PageSectionCard
    title="邮编规则"
    description="用于按国家和邮编前缀，将订单分配到目标仓库。"
  >
    <template #actions>
      <el-select
        v-model="filterCountry"
        clearable
        filterable
        placeholder="按国家筛选"
        style="width: 180px"
        @change="handleFilterChange"
      >
        <el-option
          v-for="option in countryOptions"
          :key="option.code"
          :label="option.label"
          :value="option.code"
        />
      </el-select>
      <el-button v-if="auth.hasPermission('config:edit')" type="primary" :disabled="!hasWarehouses" @click="openCreate">新增规则</el-button>
    </template>

    <div class="rule-toolbar">
      <div class="rule-summary">
        <el-tag v-if="initialized" type="info">规则数 {{ rows.length }}</el-tag>
        <el-tag v-if="filterCountry" type="primary">筛选国家 {{ currentFilterLabel }}</el-tag>
        <el-tag v-if="initialized && !hasWarehouses" type="warning">暂无可用仓库</el-tag>
      </div>
      <el-button v-if="filterCountry" text @click="clearFilter">清空筛选</el-button>
    </div>

    <el-alert
      v-if="initialized && !hasWarehouses"
      type="warning"
      :closable="false"
      show-icon
      class="page-alert"
    >
      <div class="page-alert__content">
        <span>当前暂无可用仓库，请先到仓库页面补充国家配置后，再维护邮编规则。</span>
        <el-button size="small" @click="goToWarehouses">前往仓库页</el-button>
      </div>
    </el-alert>

    <el-table
      v-loading="loading"
      :data="pagedRows"
      row-key="id"
      :empty-text="emptyTableText"
      @sort-change="handleSortChange"
    >
      <el-table-column
        label="优先级"
        prop="priority"
        width="80"
        align="center"
        sortable="custom"
        show-overflow-tooltip
      />
      <el-table-column
        label="国家"
        prop="country"
        width="120"
        sortable="custom"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          {{ countryLabel(row.country) }}
        </template>
      </el-table-column>
      <el-table-column
        label="截取前 N 位"
        prop="prefix_length"
        width="120"
        align="center"
        sortable="custom"
        show-overflow-tooltip
      />
      <el-table-column label="比较条件" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <div class="condition-cell">
            <span class="condition-badge">{{ valueTypeLabel(row.value_type) }}</span>
            <span class="condition-text">{{ ruleConditionText(row) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column
        label="目标仓库"
        prop="warehouse_name"
        min-width="220"
        sortable="custom"
      >
        <template #default="{ row }">
          <div class="warehouse-cell">
            <span>{{ warehouseName(row.warehouse_id) }}</span>
            <span v-if="warehouseCountryHint(row.warehouse_id)" class="warehouse-hint">
              {{ warehouseCountryHint(row.warehouse_id) }}
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center">
        <template #default="{ row }">
          <div class="row-actions">
            <el-button v-if="auth.hasPermission('config:edit')" link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="auth.hasPermission('config:edit')" link type="danger" @click="remove(row)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <TablePaginationBar
      v-if="initialized"
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="rows.length"
    />

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑规则' : '新增规则'"
      width="620px"
      destroy-on-close
      @closed="onDialogClosed"
    >
      <el-alert
        v-if="showWarehouseAlert"
        type="warning"
        :closable="false"
        show-icon
        class="dialog-alert"
        :title="warehouseAlertText"
      />

      <el-form :model="form" label-width="132px" class="rule-form">
        <el-form-item label="国家代码">
          <el-select
            v-model="form.country"
            filterable
            placeholder="请选择国家"
            :class="['form-field', 'form-field--sm', { 'form-field--invalid': isCountryInvalid }]"
            @change="handleCountryFieldChange"
          >
            <el-option
              v-for="option in countryOptions"
              :key="option.code"
              :label="option.label"
              :value="option.code"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="截取前 N 位">
          <el-input-number
            v-model="form.prefix_length"
            :min="1"
            :max="10"
            class="form-field form-field--xs"
          />
        </el-form-item>

        <el-form-item label="值类型">
          <el-radio-group v-model="form.value_type" class="form-field">
            <el-radio-button value="number">数字</el-radio-button>
            <el-radio-button value="string">字符串</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="比较类型">
          <el-select v-model="form.operator" class="form-field form-field--sm">
            <el-option
              v-for="operator in operatorOptions"
              :key="operator.value"
              :label="operator.label"
              :value="operator.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="比较值" class="form-item--compare-value">
          <div class="compare-value-field">
            <el-input
              v-model="form.compare_value"
              :placeholder="compareValuePlaceholder"
              :class="['form-field', { 'form-field--invalid': isCompareValueInvalid }]"
              @blur="handleCompareValueBlur"
            />
            <div v-if="compareValueValidationMessage" class="field-message field-message--error">
              {{ compareValueValidationMessage }}
            </div>
          </div>
        </el-form-item>

        <el-form-item label="目标仓库">
          <el-select
            v-model="form.warehouse_id"
            :disabled="!form.country || !hasSelectableWarehouses"
            filterable
            :no-data-text="warehouseEmptyText"
            :placeholder="warehousePlaceholder"
            :class="['form-field', { 'form-field--invalid': isWarehouseInvalid }]"
            @change="handleWarehouseFieldChange"
          >
            <el-option
              v-for="warehouse in dialogWarehouseOptions"
              :key="warehouse.id"
              :label="warehouseOptionLabel(warehouse)"
              :value="warehouse.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="1" class="form-field form-field--xs" />
        </el-form-item>

        <el-form-item label="规则预览" class="form-item--preview">
          <div class="rule-preview">
            <div class="rule-preview__grid">
              <div
                v-for="item in rulePreviewItems"
                :key="item.label"
                class="rule-preview__item"
              >
                <span class="rule-preview__label">{{ item.label }}</span>
                <span
                  :class="[
                    'rule-preview__value',
                    { 'rule-preview__value--muted': item.muted },
                  ]"
                >
                  {{ item.value }}
                </span>
              </div>
            </div>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button
          v-if="auth.hasPermission('config:edit')"
          type="primary"
          :loading="saving"
          :disabled="!form.country || !hasSelectableWarehouses"
          @click="save"
        >
          {{ editingId ? '保存修改' : '创建规则' }}
        </el-button>
      </template>
    </el-dialog>
  </PageSectionCard>
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
  type ZipcodeRuleInput,
} from '@/api/config'
import PageSectionCard from '@/components/PageSectionCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { COUNTRY_OPTIONS, getCountryLabel } from '@/utils/countries'
import {
  applyLocalSort,
  compareNumber,
  compareText,
  normalizeSortOrder,
  type SortChangeEvent,
  type SortState,
} from '@/utils/tableSort'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const NUMBER_OPERATORS = [
  { value: '=', label: '等于' },
  { value: '>=', label: '大于等于' },
  { value: '>', label: '大于' },
  { value: '!=', label: '不等于' },
  { value: '<', label: '小于' },
  { value: '<=', label: '小于等于' },
  { value: 'between', label: '区间' },
] as const

const STRING_OPERATORS = [
  { value: '=', label: '等于' },
  { value: '!=', label: '不等于' },
  { value: 'contains', label: '包含' },
  { value: 'not_contains', label: '不包含' },
] as const

const OPERATORS = [...NUMBER_OPERATORS, ...STRING_OPERATORS] as const
const countryOptions = COUNTRY_OPTIONS
const router = useRouter()

const rows = ref<ZipcodeRule[]>([])
const warehouses = ref<Warehouse[]>([])
const loading = ref(true)
const saving = ref(false)
const initialized = ref(false)
const filterCountry = ref('')
const page = ref(1)
const pageSize = ref(10)
const sortState = ref<SortState>({})

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const countryTouched = ref(false)
const compareValueTouched = ref(false)
const warehouseTouched = ref(false)
const submitAttempted = ref(false)

const form = reactive<ZipcodeRuleInput>({
  country: '',
  prefix_length: 2,
  value_type: 'number',
  operator: '>=',
  compare_value: '',
  warehouse_id: '',
  priority: 100,
})

function defaultRuleComparator(left: ZipcodeRule, right: ZipcodeRule): number {
  const countryCompare = compareText(countryLabel(left.country), countryLabel(right.country))
  if (countryCompare !== 0) return countryCompare
  return compareNumber(left.priority, right.priority)
}

const sortedRows = computed(() =>
  applyLocalSort(
    rows.value,
    sortState.value,
    {
      priority: (left, right) => compareNumber(left.priority, right.priority),
      country: (left, right) => compareText(countryLabel(left.country), countryLabel(right.country)),
      prefix_length: (left, right) => compareNumber(left.prefix_length, right.prefix_length),
      warehouse_name: (left, right) =>
        compareText(warehouseName(left.warehouse_id), warehouseName(right.warehouse_id)),
    },
    defaultRuleComparator,
  ),
)

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return sortedRows.value.slice(start, start + pageSize.value)
})

const allWarehouseOptions = computed(() =>
  [...warehouses.value].sort((left, right) => {
    const leftConfigured = Boolean(left.country)
    const rightConfigured = Boolean(right.country)
    if (leftConfigured !== rightConfigured) return leftConfigured ? -1 : 1
    return left.name.localeCompare(right.name, 'zh-CN')
  }),
)

const operatorOptions = computed(() =>
  form.value_type === 'string' ? STRING_OPERATORS : NUMBER_OPERATORS,
)

const dialogWarehouseOptions = computed(() => {
  if (!form.country) return []
  return allWarehouseOptions.value.filter((warehouse) => warehouse.country === form.country)
})

const hasWarehouses = computed(() =>
  allWarehouseOptions.value.some((warehouse) => Boolean(warehouse.country)),
)

const hasSelectableWarehouses = computed(() => dialogWarehouseOptions.value.length > 0)

const currentFilterLabel = computed(() =>
  filterCountry.value ? countryLabel(filterCountry.value) : '',
)

const needsCommaSeparatedValues = computed(
  () => form.value_type === 'string' && ['contains', 'not_contains'].includes(form.operator),
)

const BETWEEN_SEGMENT_RE = /^\d+-\d+$/
const MAX_BETWEEN_SEGMENTS = 20

const isBetweenOperator = computed(() => form.operator === 'between')

const compareValuePlaceholder = computed(() => {
  if (isBetweenOperator.value) return '例如 000-270，或多段 000-270, 500-700'
  if (form.value_type === 'number') return '请输入数字，例如 100'
  if (needsCommaSeparatedValues.value) return '请输入多个文本，使用英文逗号分隔，例如 SW, EC'
  return '请输入文本，例如 SW'
})

const compareValueValidationMessage = computed(() => {
  if (!compareValueTouched.value && !submitAttempted.value) return ''

  const value = form.compare_value.trim()
  if (!value) return '请输入比较值'

  if (isBetweenOperator.value) {
    const segments = value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
    if (segments.length === 0) return '至少需要一段区间'
    if (segments.length > MAX_BETWEEN_SEGMENTS) {
      return `区间段数不能超过 ${MAX_BETWEEN_SEGMENTS}`
    }
    const maxValue = 10 ** form.prefix_length - 1
    for (const seg of segments) {
      if (!BETWEEN_SEGMENT_RE.test(seg)) {
        return `区间格式错误：${seg}（应为 数字-数字）`
      }
      const [loStr, hiStr] = seg.split('-')
      const lo = Number(loStr)
      const hi = Number(hiStr)
      if (lo > hi) return `区间下界不能大于上界：${seg}`
      if (hi > maxValue) {
        return `上界 ${hi} 超出前 ${form.prefix_length} 位最大值 ${maxValue}`
      }
    }
    return ''
  }

  if (form.value_type === 'number' && Number.isNaN(Number(value))) {
    return '数字类型请输入有效数字'
  }

  if (needsCommaSeparatedValues.value) {
    const tokens = value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
    if (tokens.length === 0) return '请至少输入一个有效比较值'
  }

  return ''
})

const isCountryInvalid = computed(
  () => (countryTouched.value || submitAttempted.value) && !form.country,
)

const isCompareValueInvalid = computed(() => Boolean(compareValueValidationMessage.value))

const isWarehouseInvalid = computed(() => {
  if (!form.country || !hasSelectableWarehouses.value) return false
  return (warehouseTouched.value || submitAttempted.value) && !form.warehouse_id
})

const warehouseEmptyText = computed(() => {
  if (!hasWarehouses.value) return '暂无可选仓库'
  if (form.country) return '当前国家暂无可选仓库'
  return '请先选择国家代码'
})

const warehousePlaceholder = computed(() => {
  if (!form.country) return '请先选择国家代码'
  return '请选择目标仓库'
})

const emptyTableText = computed(() => {
  if (!initialized.value) return ''
  if (!hasWarehouses.value) {
    return '暂无可用仓库，请先到仓库页面补充国家配置后再维护邮编规则。'
  }
  if (filterCountry.value) {
    return `${currentFilterLabel.value} 暂无邮编规则，可点击右上角新增规则。`
  }
  return '暂无邮编规则，可点击右上角新增规则。'
})

const showWarehouseAlert = computed(
  () => !hasWarehouses.value || (Boolean(form.country) && !hasSelectableWarehouses.value),
)

const warehouseAlertText = computed(() => {
  if (!hasWarehouses.value) return '当前还没有可用仓库，请先完成仓库配置。'
  if (form.country && !hasSelectableWarehouses.value) {
    return `当前国家 ${countryLabel(form.country)} 暂无可选仓库，请先完成对应仓库配置。`
  }
  return ''
})

const rulePreviewItems = computed(() => {
  const compareValueText = form.compare_value || '未填写比较值'
  const hasCompareValue = Boolean(form.compare_value.trim())

  return [
    {
      label: '国家',
      value: form.country ? countryLabel(form.country) : '未选择国家',
      muted: !form.country,
    },
    {
      label: '截取位数',
      value: `前 ${form.prefix_length} 位`,
      muted: false,
    },
    {
      label: '比较条件',
      value: ruleConditionText({
        value_type: form.value_type,
        operator: form.operator,
        compare_value: compareValueText,
      }),
      muted: !hasCompareValue,
    },
    {
      label: '目标仓库',
      value: form.warehouse_id ? warehouseName(form.warehouse_id) : '未选择目标仓库',
      muted: !form.warehouse_id,
    },
    {
      label: '优先级',
      value: String(form.priority),
      muted: false,
    },
  ]
})

async function reload(): Promise<void> {
  loading.value = true
  try {
    rows.value = await listZipcodeRules(filterCountry.value || undefined)
  } catch (error) {
    ElMessage.error(getZipcodeRuleActionErrorMessage(error, '加载邮编规则失败'))
  } finally {
    loading.value = false
  }
}

async function loadWarehouses(): Promise<void> {
  try {
    warehouses.value = await listWarehouses()
  } catch (error) {
    ElMessage.error(getZipcodeRuleActionErrorMessage(error, '加载仓库列表失败'))
  }
}

function warehouseName(id: string): string {
  const warehouse = warehouses.value.find((item) => item.id === id)
  return warehouse ? warehouseOptionLabel(warehouse) : `已删除仓库（${id}）`
}

function warehouseCountryHint(id: string): string {
  const warehouse = warehouses.value.find((item) => item.id === id)
  if (!warehouse?.country) return ''
  return countryLabel(warehouse.country)
}

function countryLabel(code: string): string {
  return getCountryLabel(code)
}

function warehouseOptionLabel(warehouse: Warehouse): string {
  return `${warehouse.name}（${warehouse.country ? countryLabel(warehouse.country) : '未配置国家'}）`
}

function valueTypeLabel(valueType: ZipcodeRule['value_type']): string {
  return valueType === 'number' ? '数字' : '字符串'
}

function operatorLabel(operator: ZipcodeRule['operator']): string {
  return OPERATORS.find((item) => item.value === operator)?.label ?? operator
}

function ruleConditionText(
  rule: Pick<ZipcodeRule, 'value_type' | 'operator' | 'compare_value'>,
): string {
  const valueText = rule.compare_value
  if (rule.operator === 'between') {
    return `按数字区间 ${valueText}`
  }
  if (rule.operator === 'contains') {
    return `按${valueTypeLabel(rule.value_type)}包含任一 ${valueText}`
  }
  if (rule.operator === 'not_contains') {
    return `按${valueTypeLabel(rule.value_type)}不包含任一 ${valueText}`
  }
  return `按${valueTypeLabel(rule.value_type)}${operatorLabel(rule.operator)} ${valueText}`
}

function getZipcodeRuleActionErrorMessage(error: unknown, fallback: string): string {
  const message = getActionErrorMessage(error, fallback)
  const fieldLabelMap: Record<string, string> = {
    country: '国家代码',
    prefix_length: '截取前 N 位',
    value_type: '值类型',
    operator: '比较类型',
    compare_value: '比较值',
    warehouse_id: '目标仓库',
    priority: '优先级',
  }

  const fieldPrefix = Object.entries(fieldLabelMap).find(([field]) => message.startsWith(`${field}:`))
  if (fieldPrefix) {
    return message.replace(`${fieldPrefix[0]}:`, `${fieldPrefix[1]}:`)
  }

  if (message.includes('compare_value') && message.includes('number')) {
    return '比较值必须是有效数字，请检查值类型和比较值。'
  }
  if (message.includes('compare_value') && message.includes('不能为空')) {
    return '比较值不能为空。'
  }
  if (message.includes('contains') && message.includes('有效比较值')) {
    return '比较值至少需要一个有效内容，多个值请使用英文逗号分隔。'
  }
  if (message.includes('仓库') && message.includes('不匹配')) {
    return '目标仓库与所选国家不匹配，请重新选择同国家仓库。'
  }
  if (message.includes('仓库') && message.includes('不存在')) {
    return '目标仓库不存在，可能已被删除，请重新选择。'
  }
  if (message.includes('规则') && message.includes('不存在')) {
    return '当前规则不存在，列表可能已更新，请刷新后重试。'
  }
  return message
}

function resetForm(country = ''): void {
  applyForm({
    country,
    prefix_length: 2,
    value_type: 'number',
    operator: '>=',
    compare_value: '',
    warehouse_id: '',
    priority: 100,
  })
}

function applyForm(rule: ZipcodeRuleInput): void {
  Object.assign(form, rule)
}

function resetValidationState(): void {
  countryTouched.value = false
  compareValueTouched.value = false
  warehouseTouched.value = false
  submitAttempted.value = false
}

function normalizeCompareValue(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) return ''

  if (isBetweenOperator.value) {
    return trimmed
      .replace(/[，、]/g, ',')
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
      .join(', ')
  }

  if (!needsCommaSeparatedValues.value) return trimmed

  return trimmed
    .replace(/[，、]/g, ',')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .join(', ')
}

function syncOperatorByValueType(valueType: ZipcodeRule['value_type']): void {
  const allowedOperators: ZipcodeRule['operator'][] =
    valueType === 'string'
      ? STRING_OPERATORS.map((item) => item.value)
      : NUMBER_OPERATORS.map((item) => item.value)

  if (!allowedOperators.includes(form.operator)) {
    form.operator = valueType === 'string' ? '=' : '>='
  }
}

function normalizeFormForCurrentType(options?: { notify?: boolean }): void {
  syncOperatorByValueType(form.value_type)

  if (form.value_type === 'number') {
    // between 由自己的校验流程处理,不在此处要求单个数字
    if (form.operator !== 'between') {
      const trimmed = form.compare_value.trim()
      if (trimmed && Number.isNaN(Number(trimmed))) {
        form.compare_value = ''
        if (options?.notify) {
          ElMessage.warning('已切换为数字类型，原比较值不符合数字格式，已自动清空。')
        }
        return
      }
    }
  }

  form.compare_value = normalizeCompareValue(form.compare_value)
}

function buildPayload(): ZipcodeRuleInput {
  return {
    country: form.country,
    prefix_length: form.prefix_length,
    value_type: form.value_type,
    operator: form.operator,
    compare_value: normalizeCompareValue(form.compare_value),
    warehouse_id: form.warehouse_id,
    priority: form.priority,
  }
}

function openCreate(): void {
  editingId.value = null
  resetValidationState()
  resetForm(filterCountry.value || '')
  dialogVisible.value = true
}

function openEdit(row: ZipcodeRule): void {
  editingId.value = row.id
  resetValidationState()
  applyForm({
    country: row.country,
    prefix_length: row.prefix_length,
    value_type: row.value_type,
    operator: row.operator,
    compare_value: row.compare_value,
    warehouse_id: row.warehouse_id,
    priority: row.priority,
  })
  normalizeFormForCurrentType()
  dialogVisible.value = true
}

function onDialogClosed(): void {
  editingId.value = null
  resetValidationState()
  resetForm()
}

function handleFilterChange(): void {
  page.value = 1
  void reload()
}

function clearFilter(): void {
  filterCountry.value = ''
  handleFilterChange()
}

function handleSortChange({ prop, order }: SortChangeEvent): void {
  const normalizedOrder = normalizeSortOrder(order)
  sortState.value = normalizedOrder && prop ? { prop, order: normalizedOrder } : {}
  page.value = 1
}

function goToWarehouses(): void {
  void router.push('/data/warehouses')
}

async function save(): Promise<void> {
  submitAttempted.value = true

  if (!form.country) {
    ElMessage.warning('请选择国家代码')
    return
  }
  if (compareValueValidationMessage.value) {
    ElMessage.warning(compareValueValidationMessage.value)
    return
  }
  if (!form.warehouse_id) {
    ElMessage.warning('请选择目标仓库')
    return
  }

  saving.value = true
  try {
    form.compare_value = normalizeCompareValue(form.compare_value)
    const payload = buildPayload()
    if (editingId.value) {
      await updateZipcodeRule(editingId.value, payload)
    } else {
      await createZipcodeRule(payload)
    }
    dialogVisible.value = false
    ElMessage.success('已保存')
    await reload()
  } catch (error) {
    ElMessage.error(getZipcodeRuleActionErrorMessage(error, '保存失败'))
  } finally {
    saving.value = false
  }
}

function handleCompareValueBlur(): void {
  compareValueTouched.value = true
  form.compare_value = normalizeCompareValue(form.compare_value)
}

function handleCountryFieldChange(): void {
  countryTouched.value = true
}

function handleWarehouseFieldChange(): void {
  warehouseTouched.value = true
}

async function remove(row: ZipcodeRule): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除规则 #${row.id} 吗？`, '删除规则', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteZipcodeRule(row.id)
    ElMessage.success('已删除')
    await reload()
  } catch (error) {
    ElMessage.error(getZipcodeRuleActionErrorMessage(error, '删除失败'))
  }
}

onMounted(async () => {
  try {
    await loadWarehouses()
    await reload()
  } finally {
    initialized.value = true
  }
})

watch([() => rows.value.length, pageSize], () => {
  const totalPages = Math.max(1, Math.ceil(rows.value.length / pageSize.value))
  if (page.value > totalPages) {
    page.value = totalPages
  }
})

watch(
  () => form.value_type,
  () => {
    normalizeFormForCurrentType({ notify: compareValueTouched.value || submitAttempted.value })
  },
)

watch(
  () => form.operator,
  () => {
    form.compare_value = normalizeCompareValue(form.compare_value)
  },
)

watch(
  () => form.country,
  (country, previousCountry) => {
    if (!form.warehouse_id) return

    const selectedWarehouse = warehouses.value.find((item) => item.id === form.warehouse_id)
    if (!selectedWarehouse) {
      form.warehouse_id = ''
      return
    }

    if (country && selectedWarehouse.country !== country) {
      form.warehouse_id = ''
      warehouseTouched.value = false
      if (previousCountry && previousCountry !== country) {
        ElMessage.warning('国家已切换，目标仓库已按新国家自动清空，请重新选择。')
      }
    }
  },
)
</script>

<style lang="scss" scoped>
:deep(.el-dialog) {
  overflow: hidden;
  border: 1px solid $color-border-default;
  border-radius: $radius-xl;
  background: $color-bg-card;
  box-shadow: $shadow-popup;
}

:deep(.el-dialog__header) {
  display: flex;
  align-items: center;
  min-height: 52px;
  margin-right: 0;
  padding: 0 $space-6;
  border-bottom: 1px solid $color-border-subtle;
}

:deep(.el-dialog__title) {
  color: $color-text-primary;
  font-size: $font-size-sm;
  font-weight: $font-weight-semibold;
  letter-spacing: $tracking-tight;
}

:deep(.el-dialog__headerbtn) {
  top: 0;
  right: $space-4;
  width: 40px;
  height: 52px;

  &:hover {
    background: $color-bg-subtle;
    border-radius: $radius-md;
  }
}

:deep(.el-dialog__body) {
  padding: $space-5 $space-6 $space-6;
}

:deep(.el-dialog__footer) {
  display: flex;
  justify-content: flex-end;
  gap: $space-2;
  padding: $space-4 $space-6;
  border-top: 1px solid $color-border-subtle;
  background: $color-bg-card;
}

:deep(.el-dialog__footer .el-button.is-disabled) {
  opacity: 1;
  border-color: $color-border-default;
  background: $color-bg-subtle;
  color: $color-text-disabled;
  box-shadow: none;
}

:deep(.el-dialog__footer .el-button) {
  min-width: 88px;
}

.rule-form {
  :deep(.el-form-item) {
    display: flex;
    align-items: center;
    margin-bottom: $space-4;
  }

  :deep(.el-form-item__label) {
    display: inline-flex;
    align-items: center;
    justify-content: flex-end;
    min-height: 40px;
    padding-bottom: 0;
    color: $color-text-secondary;
    font-size: $font-size-sm;
    font-weight: $font-weight-medium;
    line-height: $line-height-normal;
  }

  :deep(.el-form-item__content) {
    display: flex;
    align-items: center;
    min-height: 40px;
    line-height: $line-height-normal;
  }

  :deep(.el-input-number) {
    display: inline-flex;
    align-items: stretch;
    height: 40px;

    &:hover:not(.is-disabled) .el-input__wrapper {
      box-shadow: 0 0 0 1px $color-border-strong inset !important;
    }
  }

  :deep(.el-input-number__decrease),
  :deep(.el-input-number__increase) {
    top: 0;
    height: 40px;
    border-color: $color-border-default;
    background: $color-bg-card;
    color: $color-text-secondary;
    transition: $transition-fast;

    &:hover {
      background: $color-bg-subtle;
      color: $color-text-primary;
    }
  }

  :deep(.el-input-number .el-input__wrapper) {
    min-height: 40px;
  }

  :deep(.el-input-number.is-disabled .el-input__wrapper),
  :deep(.el-input.is-disabled .el-input__wrapper),
  :deep(.el-select.is-disabled .el-select__wrapper) {
    background: $color-bg-subtle !important;
    box-shadow: 0 0 0 1px $color-border-default inset !important;
    color: $color-text-disabled;
    cursor: not-allowed;
    opacity: 0.9;
  }

  :deep(.el-input.is-disabled .el-input__inner),
  :deep(.el-select.is-disabled .el-select__placeholder),
  :deep(.el-select.is-disabled .el-select__selected-item) {
    color: $color-text-disabled !important;
    cursor: not-allowed;
  }

  :deep(.el-radio-group) {
    display: inline-flex;
    align-items: center;
    width: auto;
    min-height: 40px;
    overflow: hidden;
    border: 1px solid $color-border-default;
    border-radius: $radius-md;
    background: $color-bg-card;
    box-shadow: $shadow-sm;
  }

  :deep(.el-radio-button) {
    display: inline-flex;
  }

  :deep(.el-radio-button__inner) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 76px;
    height: 36px;
    border: 0;
    border-radius: 0;
    background: $color-bg-card;
    box-shadow: none;
    color: $color-text-secondary;
    font-weight: $font-weight-medium;
    transition: $transition-fast;
  }

  :deep(.el-radio-button:not(.is-active) .el-radio-button__inner:hover) {
    background: $color-bg-subtle;
    color: $color-text-primary;
  }

  :deep(.el-radio-button.is-active .el-radio-button__inner) {
    background: $color-brand-primary;
    box-shadow: none;
    color: $color-brand-primary-fg;
  }

  :deep(.el-radio-button + .el-radio-button .el-radio-button__inner) {
    border-left: 1px solid $color-border-default;
  }

  :deep(.form-item--compare-value),
  :deep(.form-item--preview) {
    align-items: flex-start;
  }

  :deep(.form-item--compare-value .el-form-item__label) {
    min-height: 40px;
    padding-top: $space-2;
  }

  :deep(.form-item--compare-value .el-form-item__content),
  :deep(.form-item--preview .el-form-item__content) {
    align-items: flex-start;
    min-height: auto;
  }

  :deep(.form-item--preview .el-form-item__label) {
    min-height: 40px;
    padding-top: $space-3;
  }
}

.dialog-alert {
  margin-bottom: $space-4;
  border: 1px solid $color-warning-border;
  border-radius: $radius-md;
  background: $color-warning-soft;

  :deep(.el-alert__title) {
    color: $color-text-primary;
    font-size: $font-size-sm;
    font-weight: $font-weight-medium;
    line-height: $line-height-normal;
  }
}

.page-alert {
  margin-bottom: $space-4;
  border: 1px solid $color-warning-border;
  border-radius: $radius-md;
  background: $color-warning-soft;
}

.page-alert__content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $space-3;
  width: 100%;
}

.rule-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $space-3;
  margin-bottom: $space-4;
}

.rule-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: $space-2;
}

.row-actions {
  display: inline-flex;
  align-items: center;
  gap: $space-2;
}

.warehouse-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.warehouse-hint {
  color: $color-text-secondary;
  font-size: $font-size-xs;
}

.form-field {
  width: 320px;
}

.form-field--sm {
  width: 220px;
}

.form-field--xs {
  width: 140px;
}

.compare-value-field {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  width: 320px;
}

.field-message {
  margin-top: $space-2;
  font-size: $font-size-xs;
  line-height: $line-height-normal;
}

.field-message--error {
  color: $color-danger;
}

.form-field--invalid {
  :deep(.el-input__wrapper),
  :deep(.el-select__wrapper) {
    background: $color-bg-card !important;
    box-shadow: 0 0 0 1px $color-danger inset !important;
  }

  :deep(.el-input__wrapper:hover),
  :deep(.el-select__wrapper:hover),
  :deep(.el-input__wrapper.is-focus),
  :deep(.el-select__wrapper.is-focused) {
    box-shadow:
      0 0 0 2px $color-bg-card inset,
      0 0 0 3px $color-danger inset !important;
  }
}

.condition-text {
  color: $color-text-primary;
  font-size: $font-size-sm;
  line-height: $line-height-normal;
  word-break: break-word;
}

.condition-cell {
  display: flex;
  align-items: flex-start;
  gap: $space-2;
}

.condition-badge {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border: 1px solid $color-border-default;
  border-radius: $radius-md;
  background: $color-bg-subtle;
  color: $color-text-secondary;
  font-size: $font-size-xs;
  font-weight: $font-weight-medium;
}

.rule-preview {
  width: 100%;
  min-height: 88px;
  padding: $space-3 $space-4;
  border: 1px solid $color-border-default;
  border-radius: $radius-md;
  background: $color-bg-card;
  box-shadow: $shadow-sm;
  color: $color-text-primary;
  font-size: $font-size-sm;
  line-height: $line-height-normal;
}

.rule-preview__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: $space-3 $space-4;
}

.rule-preview__item {
  display: flex;
  flex-direction: column;
  gap: $space-1;
  min-width: 0;
}

.rule-preview__label {
  color: $color-text-secondary;
  font-size: $font-size-xs;
  font-weight: $font-weight-medium;
  letter-spacing: $tracking-wide;
}

.rule-preview__value {
  color: $color-text-primary;
  font-size: $font-size-sm;
  font-weight: $font-weight-medium;
  line-height: $line-height-normal;
  word-break: break-word;
}

.rule-preview__value--muted {
  color: $color-text-secondary;
  font-weight: $font-weight-normal;
}

@media (max-width: 900px) {
  .rule-toolbar,
  .page-alert__content {
    flex-direction: column;
    align-items: flex-start;
  }

  .rule-preview__grid {
    grid-template-columns: 1fr;
  }
}
</style>
