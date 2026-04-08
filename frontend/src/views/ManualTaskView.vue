<template>
  <div class="manual-tasks">
    <el-card shadow="never">
      <template #header>
        <span class="card-title">手动同步 / 计算</span>
      </template>

      <div class="action-grid">
        <div v-for="action in actions" :key="action.key" class="action-card">
          <div class="action-info">
            <h3>{{ action.label }}</h3>
            <p>{{ action.desc }}</p>
          </div>
          <el-button
            type="primary"
            :loading="loading[action.key] || false"
            @click="trigger(action)"
          >
            执行
          </el-button>
        </div>
      </div>
    </el-card>

    <TaskProgress
      v-if="currentTaskId"
      :task-id="currentTaskId"
      @terminal="onDone"
    />
  </div>
</template>

<script setup lang="ts">
import client from '@/api/client'
import TaskProgress from '@/components/TaskProgress.vue'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'

interface Action {
  key: string
  label: string
  desc: string
  url: string
}

const actions: Action[] = [
  { key: 'all', label: '全量同步', desc: '触发所有同步任务', url: '/api/sync/all' },
  { key: 'product', label: '同步在线产品信息', desc: '获取已配对产品 + commodity_id 映射', url: '/api/sync/product-listing' },
  { key: 'warehouse', label: '同步仓库列表', desc: '拉取赛狐仓库主数据', url: '/api/sync/warehouse' },
  { key: 'inventory', label: '同步库存明细', desc: '更新可用 + 占用库存', url: '/api/sync/inventory' },
  { key: 'transit', label: '同步在途数据', desc: '从其他出库列表拉取在途中', url: '/api/sync/out-records' },
  { key: 'orders', label: '同步订单', desc: '增量拉取订单列表 + 详情', url: '/api/sync/orders' },
  { key: 'engine', label: '运行规则引擎', desc: '生成新建议单（会归档旧单）', url: '/api/engine/run' }
]

const loading = reactive<Record<string, boolean>>({})
const currentTaskId = ref<number | null>(null)

async function trigger(action: Action): Promise<void> {
  loading[action.key] = true
  try {
    const { data } = await client.post<{ task_id: number; existing: boolean }>(action.url)
    currentTaskId.value = data.task_id
    if (data.existing) {
      ElMessage.warning('已有同名任务在运行，复用其进度')
    } else {
      ElMessage.success('任务已入队')
    }
  } catch {
    ElMessage.error('任务触发失败')
  } finally {
    loading[action.key] = false
  }
}

function onDone(): void {
  ElMessage.info('任务完成')
  currentTaskId.value = null
}
</script>

<style lang="scss" scoped>
.manual-tasks {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}
.card-title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}
.action-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: $space-4;
}
.action-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: $color-bg-subtle;
  border-radius: $radius-lg;
  padding: $space-4 $space-5;
  .action-info {
    h3 {
      margin: 0 0 $space-1 0;
      font-size: $font-size-md;
      font-weight: $font-weight-semibold;
    }
    p {
      margin: 0;
      color: $color-text-secondary;
      font-size: $font-size-xs;
    }
  }
}
</style>
