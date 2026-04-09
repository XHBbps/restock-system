<template>
  <el-card v-if="form" shadow="never">
    <template #header>
      <span class="card-title">全局参数</span>
    </template>

    <el-form :model="form" label-width="200px" style="max-width: 640px">
      <el-form-item label="国内中心仓周转天数">
        <el-input-number v-model="form.buffer_days" :min="1" :max="365" />
      </el-form-item>
      <el-form-item label="海外仓目标库存天数">
        <el-input-number v-model="form.target_days" :min="1" :max="365" />
      </el-form-item>
      <el-form-item label="默认采购提前期(天)">
        <el-input-number v-model="form.lead_time_days" :min="0" :max="365" />
      </el-form-item>
      <el-form-item label="同步间隔(分钟)">
        <el-input-number v-model="form.sync_interval_minutes" :min="5" :max="1440" />
      </el-form-item>
      <el-form-item label="规则引擎 cron">
        <el-select v-model="selectedCronPreset" style="width: 200px" @change="onCronPresetChange">
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
          placeholder="0 8 * * *"
          style="width: 200px; margin-left: 12px"
          @input="onCustomCronInput"
        />
      </el-form-item>
      <el-form-item label="默认采购主仓 ID">
        <el-input v-model="form.default_purchase_warehouse_id" placeholder="赛狐 warehouse.id" />
      </el-form-item>
      <el-form-item label="是否含税">
        <el-radio-group v-model="form.include_tax">
          <el-radio-button value="0">不含税</el-radio-button>
          <el-radio-button value="1">含税</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="店铺同步模式">
        <el-radio-group v-model="form.shop_sync_mode">
          <el-radio-button value="all">全量</el-radio-button>
          <el-radio-button value="specific">指定店铺</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { getGlobalConfig, patchGlobalConfig, type GlobalConfig } from '@/api/config'
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

const form = ref<GlobalConfig | null>(null)
const saving = ref(false)

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
  const match = cronPresets.find((p) => p.value === form.value!.calc_cron)
  if (match && match.value !== '__custom__') {
    selectedCronPreset.value = match.value
  } else {
    selectedCronPreset.value = '__custom__'
    customCron.value = form.value.calc_cron || ''
  }
}

function onCronPresetChange(val: string): void {
  if (!form.value) return
  if (val === '__custom__') {
    customCron.value = form.value.calc_cron || ''
  } else {
    form.value.calc_cron = val
  }
}

function onCustomCronInput(val: string): void {
  if (form.value) {
    form.value.calc_cron = val
  }
}

onMounted(async () => {
  form.value = await getGlobalConfig()
  initCronState()
})

async function save(): Promise<void> {
  if (!form.value) return
  saving.value = true
  try {
    form.value = await patchGlobalConfig(form.value)
    ElMessage.success('已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style lang="scss" scoped>
.card-title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}
</style>
