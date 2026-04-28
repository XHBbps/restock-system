<template>
  <PageSectionCard v-if="toggle" title="采补建议生成开关" class="toggle-section">
    <div class="toggle-row">
      <el-tooltip
        :disabled="toggle.enabled || toggle.can_enable"
        :content="toggle.can_enable_reason || '当前不可开启'"
        placement="top"
      >
        <el-switch
          v-model="toggleValue"
          :loading="togglePatching"
          :disabled="!auth.hasPermission('restock:new_cycle') || (!toggle.enabled && !toggle.can_enable)"
          :active-text="toggleValue ? '已开启' : '已关闭'"
          @change="onToggleChange"
        />
      </el-tooltip>
      <div class="toggle-meta">
        <div>最近操作人：{{ toggle.updated_by_name ?? '—' }}</div>
        <div>最近操作时间：{{ toggle.updated_at ? formatDateTime(toggle.updated_at) : '—' }}</div>
        <el-tag v-if="!toggle.enabled && !toggle.can_enable" type="warning">
          无法开启：{{ toggle.can_enable_reason }}
        </el-tag>
      </div>
    </div>
    <div class="toggle-hint">
      <span v-if="!auth.hasPermission('restock:new_cycle')">你没有操作此开关的权限（需要 <code>restock:new_cycle</code>）。</span>
      <span v-else>打开开关会归档当前采补建议，进入新一轮生成周期。</span>
    </div>
  </PageSectionCard>

  <PageSectionCard v-if="form" title="全局参数">
    <template #actions>
      <el-button type="primary" :loading="saving" :disabled="!auth.hasPermission('config:edit')" @click="save">保存</el-button>
    </template>

    <div class="config-sections">
      <div class="config-section">
        <div class="section-label">采补参数</div>
        <el-alert
          v-if="unknownCountryCodes.length"
          class="country-discovery-alert"
          type="warning"
          :closable="false"
          show-icon
          :title="`新发现国家：${unknownCountryCodes.join('、')}`"
        />
        <el-form :model="form" label-width="180px" style="max-width: 620px">
          <el-form-item label="国内中心仓周转天数">
            <el-input-number v-model="form.buffer_days" :min="1" :max="365" />
          </el-form-item>
          <el-form-item label="海外仓目标库存天数">
            <el-input-number v-model="form.target_days" :min="1" :max="365" />
          </el-form-item>
          <el-form-item label="默认采购提前期">
            <el-input-number v-model="form.lead_time_days" :min="0" :max="365" />
          </el-form-item>
          <el-form-item label="安全库存天数">
            <el-input-number v-model="form.safety_stock_days" :min="1" :max="90" />
          </el-form-item>
          <el-form-item label="补货区域">
            <el-select
              v-model="form.restock_regions"
              class="full-width-control"
              multiple
              collapse-tags
              collapse-tags-tooltip
              filterable
              clearable
              placeholder="未选择时默认全部国家参与计算"
            >
              <el-option
                v-for="option in countryOptions"
                :key="option.code"
                :label="option.label"
                :value="option.code"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="EU 成员国">
            <el-select
              v-model="form.eu_countries"
              class="full-width-control"
              multiple
              collapse-tags
              collapse-tags-tooltip
              filterable
              clearable
            >
              <el-option
                v-for="option in euCountryOptions"
                :key="option.code"
                :label="option.label"
                :value="option.code"
              />
            </el-select>
          </el-form-item>
        </el-form>
      </div>

      <div class="config-section">
        <div class="section-label">同步设置</div>
        <el-form :model="form" label-width="180px" style="max-width: 620px">
          <el-form-item label="同步间隔(分钟)">
            <el-input-number v-model="form.sync_interval_minutes" :min="5" :max="1440" />
          </el-form-item>
          <el-form-item label="调度器开关">
            <el-switch v-model="form.scheduler_enabled" />
          </el-form-item>
          <el-form-item label="店铺同步模式">
            <el-radio-group v-model="form.shop_sync_mode" class="segmented-radio-group">
              <el-radio-button value="all">全量</el-radio-button>
              <el-radio-button value="specific">指定店铺</el-radio-button>
            </el-radio-group>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </PageSectionCard>
</template>

<script setup lang="ts">
import {
  getCountryOptions,
  getGenerationToggle,
  getGlobalConfig,
  patchGenerationToggle,
  patchGlobalConfig,
  type CountryOption as DynamicCountryOption,
  type GenerationToggle,
  type GlobalConfig,
} from '@/api/config'
import PageSectionCard from '@/components/PageSectionCard.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { COUNTRY_OPTIONS } from '@/utils/countries'
import { useAuthStore } from '@/stores/auth'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

const auth = useAuthStore()
const form = ref<GlobalConfig | null>(null)
const saving = ref(false)
const countryOptions = ref<DynamicCountryOption[]>(
  COUNTRY_OPTIONS.map((option) => ({
    ...option,
    builtin: true,
    observed: false,
    can_be_eu_member: !['EU', 'ZZ'].includes(option.code),
  })),
)
const unknownCountryCodes = ref<string[]>([])

const toggle = ref<GenerationToggle | null>(null)
const toggleValue = ref(false)
const togglePatching = ref(false)

const euCountryOptions = computed(() =>
  countryOptions.value.filter((option) => option.can_be_eu_member),
)

function formatDateTime(value: string | null | undefined): string {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '—'
}

let savedCalcParams = {
  target_days: 0,
  buffer_days: 0,
  lead_time_days: 0,
  safety_stock_days: 0,
  restock_regions: [] as string[],
  eu_countries: [] as string[],
}

function sameArray(left: string[], right: string[]): boolean {
  return JSON.stringify(left) === JSON.stringify(right)
}

function snapshotCalcParams(): void {
  if (!form.value) return
  savedCalcParams = {
    target_days: form.value.target_days,
    buffer_days: form.value.buffer_days,
    lead_time_days: form.value.lead_time_days,
    safety_stock_days: form.value.safety_stock_days,
    restock_regions: [...form.value.restock_regions],
    eu_countries: [...form.value.eu_countries],
  }
}

function calcParamsChanged(): boolean {
  if (!form.value) return false
  return (
    form.value.target_days !== savedCalcParams.target_days ||
    form.value.buffer_days !== savedCalcParams.buffer_days ||
    form.value.lead_time_days !== savedCalcParams.lead_time_days ||
    form.value.safety_stock_days !== savedCalcParams.safety_stock_days ||
    !sameArray(form.value.restock_regions, savedCalcParams.restock_regions) ||
    !sameArray(form.value.eu_countries, savedCalcParams.eu_countries)
  )
}

async function loadToggle(): Promise<void> {
  try {
    const nextToggle = await getGenerationToggle()
    toggle.value = nextToggle
    toggleValue.value = nextToggle.enabled
  } catch {
    toggle.value = null
  }
}

async function loadCountryOptions(): Promise<void> {
  try {
    const resp = await getCountryOptions()
    countryOptions.value = resp.items
    unknownCountryCodes.value = resp.unknown_country_codes
  } catch {
    unknownCountryCodes.value = []
  }
}

onMounted(async () => {
  try {
    await loadCountryOptions()
    form.value = await getGlobalConfig()
    snapshotCalcParams()
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '加载全局配置失败'))
    return
  }
  await loadToggle()
})

async function onToggleChange(next: boolean | string | number): Promise<void> {
  const target = Boolean(next)
  const prev = !target
  if (target) {
    if (toggle.value && !toggle.value.can_enable) {
      ElMessage.warning(toggle.value.can_enable_reason || '当前不可开启')
      toggleValue.value = prev
      return
    }
    try {
      await ElMessageBox.confirm(
        '将归档当前采补建议并开启新周期，确定继续？',
        '确认开启生成开关',
        { type: 'warning', confirmButtonText: '确认开启', cancelButtonText: '取消' },
      )
    } catch {
      toggleValue.value = prev
      return
    }
  }
  togglePatching.value = true
  try {
    const updated = await patchGenerationToggle(target)
    toggle.value = updated
    toggleValue.value = updated.enabled
    ElMessage.success(target ? '开关已开启' : '开关已关闭')
  } catch (error) {
    toggleValue.value = prev
    ElMessage.error(getActionErrorMessage(error, '开关切换失败'))
  } finally {
    togglePatching.value = false
  }
}

async function save(): Promise<void> {
  if (!form.value) return
  if (form.value.target_days < form.value.lead_time_days) {
    ElMessage.error('目标库存天数不能小于采购提前期')
    return
  }
  saving.value = true
  try {
    const changed = calcParamsChanged()
    form.value = await patchGlobalConfig(form.value)
    snapshotCalcParams()
    ElMessage.success('已保存')
    if (changed) {
      ElMessage.warning({
        message: '采补参数已变更，建议重新生成采补建议单。',
        duration: 5000,
      })
    }
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '保存失败'))
  } finally {
    saving.value = false
  }
}
</script>

<style lang="scss" scoped>
.config-sections {
  display: flex;
  flex-direction: column;
  gap: $space-5;
}

.section-label {
  font-size: $font-size-sm;
  font-weight: $font-weight-semibold;
  margin-bottom: $space-3;
  color: $color-text-primary;
}

:deep(.el-form-item) {
  align-items: center;
  margin-bottom: $space-4;
}

:deep(.el-form-item__label) {
  line-height: 32px;
  padding-bottom: 0;
}

:deep(.el-form-item__content) {
  line-height: 32px;
}

.full-width-control {
  width: 100%;
}

.toggle-section {
  margin-bottom: $space-4;
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: $space-4;
}

.toggle-meta {
  display: flex;
  flex-direction: column;
  gap: $space-1;
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.toggle-hint {
  margin-top: $space-3;
  color: $color-text-secondary;
  font-size: $font-size-xs;
}

.country-discovery-alert {
  max-width: 620px;
  margin-bottom: $space-4;
}
</style>
