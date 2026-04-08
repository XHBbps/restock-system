<template>
  <el-card v-if="form" shadow="never">
    <template #header>
      <span class="card-title">全局参数</span>
    </template>

    <el-form :model="form" label-width="200px" style="max-width: 640px">
      <el-form-item label="国内中心仓周转天数">
        <el-input-number v-model="form.buffer_days" :min="1" :max="365" />
        <span class="hint">BUFFER_DAYS — Step 4 公式</span>
      </el-form-item>
      <el-form-item label="海外仓目标库存天数">
        <el-input-number v-model="form.target_days" :min="1" :max="365" />
        <span class="hint">TARGET_DAYS — Step 3 / Step 6 公式</span>
      </el-form-item>
      <el-form-item label="默认采购提前期(天)">
        <el-input-number v-model="form.lead_time_days" :min="0" :max="365" />
        <span class="hint">LEAD_TIME_DAYS — SKU 级 lead_time 缺省时使用</span>
      </el-form-item>
      <el-form-item label="同步间隔(分钟)">
        <el-input-number v-model="form.sync_interval_minutes" :min="5" :max="1440" />
      </el-form-item>
      <el-form-item label="规则引擎 cron">
        <el-input v-model="form.calc_cron" placeholder="0 8 * * *" />
        <span class="hint">默认每天 08:00 北京时间</span>
      </el-form-item>
      <el-form-item label="默认采购主仓 ID">
        <el-input v-model="form.default_purchase_warehouse_id" placeholder="赛狐 warehouse.id" />
        <span class="hint">推送采购单时使用</span>
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

onMounted(async () => {
  form.value = await getGlobalConfig()
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
.hint {
  margin-left: $space-3;
  color: $color-text-secondary;
  font-size: $font-size-xs;
}
</style>
