<template>
  <PageSectionCard v-if="toggle" title="补货建议生成开关" class="toggle-section">
    <div class="toggle-row">
      <el-switch
        v-model="toggleValue"
        :loading="togglePatching"
        :disabled="!auth.hasPermission('restock:new_cycle')"
        :active-text="toggleValue ? '已开启' : '已关闭'"
        @change="onToggleChange"
      />
      <div class="toggle-meta">
        <div>最近操作人：{{ toggle.updated_by_name ?? '—' }}</div>
        <div>最近操作时间：{{ toggle.updated_at ? formatDateTime(toggle.updated_at) : '—' }}</div>
      </div>
    </div>
    <div class="toggle-hint">
      <span v-if="!auth.hasPermission('restock:new_cycle')">你没有翻开关的权限（需要 <code>restock:new_cycle</code>）。</span>
      <span v-else>打开开关会归档所有草稿建议单。</span>
    </div>
  </PageSectionCard>

  <PageSectionCard v-if="form" title="全局参数">
    <template #actions>
      <el-button type="primary" :loading="saving" :disabled="!auth.hasPermission('config:edit')" @click="save">保存</el-button>
    </template>

    <div class="config-sections">
      <div class="config-section">
        <div class="section-label">补货参数</div>
        <el-form :model="form" label-width="180px" style="max-width: 560px">
          <el-form-item label="国内中心仓周转天数">
            <el-input-number v-model="form.buffer_days" :min="1" :max="365" />
          </el-form-item>
          <el-form-item label="海外仓目标库存天数">
            <el-input-number v-model="form.target_days" :min="1" :max="365" />
          </el-form-item>
          <el-form-item label="默认采购提前期">
            <el-input-number v-model="form.lead_time_days" :min="0" :max="365" />
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
                v-for="option in COUNTRY_OPTIONS"
                :key="option.code"
                :label="option.label"
                :value="option.code"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="默认采购主仓 ID">
            <el-input
              v-model="form.default_purchase_warehouse_id"
              placeholder="外部仓库 ID"
            />
          </el-form-item>
        </el-form>
      </div>

      <div class="config-section">
        <div class="section-label">同步设置</div>
        <el-form :model="form" label-width="180px" style="max-width: 560px">
          <el-form-item label="同步间隔(分钟)">
            <el-input-number v-model="form.sync_interval_minutes" :min="5" :max="1440" />
          </el-form-item>
          <el-form-item label="店铺同步模式">
            <el-radio-group v-model="form.shop_sync_mode">
              <el-radio-button value="all">全量</el-radio-button>
              <el-radio-button value="specific">指定店铺</el-radio-button>
            </el-radio-group>
          </el-form-item>
        </el-form>
      </div>

      <div class="config-section">
        <div class="section-label">补货计算</div>
        <el-form :model="form" label-width="180px" style="max-width: 560px">
          <el-form-item label="自动计算">
            <el-switch v-model="form.calc_enabled" />
          </el-form-item>
          <el-form-item v-if="form.calc_enabled" label="自动计算时间">
            <div class="cron-inline">
              <el-select
                v-model="selectedCronPreset"
                class="cron-select"
                @change="onCronPresetChange"
              >
                <el-option
                  v-for="preset in cronPresets"
                  :key="preset.value"
                  :label="preset.label"
                  :value="preset.value"
                />
              </el-select>
              <el-input
                v-if="selectedCronPreset === '__custom__'"
                v-model="customCron"
                class="cron-input"
                placeholder="如: 30 6 1,15 * *"
                @input="onCustomCronInput"
              />
            </div>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </PageSectionCard>
</template>

<script setup lang="ts">
import {
  getGenerationToggle,
  getGlobalConfig,
  patchGenerationToggle,
  patchGlobalConfig,
  type GenerationToggle,
  type GlobalConfig,
} from '@/api/config'
import PageSectionCard from '@/components/PageSectionCard.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { COUNTRY_OPTIONS } from '@/utils/countries'
import { useAuthStore } from '@/stores/auth'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'

const auth = useAuthStore()
const form = ref<GlobalConfig | null>(null)
const saving = ref(false)

const toggle = ref<GenerationToggle | null>(null)
const toggleValue = ref(false)
const togglePatching = ref(false)

function formatDateTime(value: string | null | undefined): string {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '—'
}

let savedCalcParams = {
  target_days: 0,
  buffer_days: 0,
  lead_time_days: 0,
  restock_regions: [] as string[],
}

function sameRestockRegions(left: string[], right: string[]): boolean {
  return JSON.stringify(left) === JSON.stringify(right)
}

function snapshotCalcParams(): void {
  if (!form.value) return
  savedCalcParams = {
    target_days: form.value.target_days,
    buffer_days: form.value.buffer_days,
    lead_time_days: form.value.lead_time_days,
    restock_regions: [...form.value.restock_regions],
  }
}

function calcParamsChanged(): boolean {
  if (!form.value) return false
  return (
    form.value.target_days !== savedCalcParams.target_days ||
    form.value.buffer_days !== savedCalcParams.buffer_days ||
    form.value.lead_time_days !== savedCalcParams.lead_time_days ||
    !sameRestockRegions(form.value.restock_regions, savedCalcParams.restock_regions)
  )
}

const cronPresets = [
  { label: '每天 06:00', value: '0 6 * * *' },
  { label: '每天 08:00', value: '0 8 * * *' },
  { label: '每天 12:00', value: '0 12 * * *' },
  { label: '每天 20:00', value: '0 20 * * *' },
  { label: '每 12 小时', value: '0 */12 * * *' },
  { label: '每 6 小时', value: '0 */6 * * *' },
  { label: '自定义', value: '__custom__' },
]

const selectedCronPreset = ref('__custom__')
const customCron = ref('')

function initCronState(): void {
  if (!form.value) return
  const match = cronPresets.find((preset) => preset.value === form.value?.calc_cron)
  if (match && match.value !== '__custom__') {
    selectedCronPreset.value = match.value
  } else {
    selectedCronPreset.value = '__custom__'
    customCron.value = form.value.calc_cron || ''
  }
}

function onCronPresetChange(value: string): void {
  if (!form.value) return
  if (value === '__custom__') {
    customCron.value = form.value.calc_cron || ''
    return
  }
  form.value.calc_cron = value
}

function onCustomCronInput(value: string): void {
  if (!form.value) return
  form.value.calc_cron = value
}

onMounted(async () => {
  try {
    form.value = await getGlobalConfig()
    snapshotCalcParams()
    initCronState()
    const t = await getGenerationToggle()
    toggle.value = t
    toggleValue.value = t.enabled
  } catch (e) {
    ElMessage.error(getActionErrorMessage(e, '加载全局配置'))
  }
})

async function onToggleChange(next: boolean | string | number): Promise<void> {
  const target = Boolean(next)
  const prev = !target
  if (target) {
    try {
      await ElMessageBox.confirm(
        '打开开关将归档所有草稿建议单，确认继续？',
        '打开生成开关',
        { type: 'warning', confirmButtonText: '确认打开', cancelButtonText: '取消' },
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
    ElMessage.success(target ? '开关已打开，已归档所有草稿' : '开关已关闭')
  } catch (err) {
    toggleValue.value = prev
    ElMessage.error(getActionErrorMessage(err, '开关切换失败'))
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
    initCronState()
    ElMessage.success('已保存')
    if (changed) {
      ElMessage.warning({
        message:
          '补货参数已变更（目标天数、周转天数、提前期、补货区域），建议重新生成补货建议单。',
        duration: 5000,
      })
    }
  } catch (err) {
    ElMessage.error(getActionErrorMessage(err, '保存失败'))
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

.cron-inline {
  display: flex;
  align-items: center;
  gap: $space-2;
  width: 100%;
}

.cron-select {
  width: 120px;
  flex-shrink: 0;
}

.cron-input {
  flex: 1;
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
</style>
